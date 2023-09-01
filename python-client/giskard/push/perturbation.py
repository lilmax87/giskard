"""
Trigger functions for model debugging prediction notifications.

Functions:

- create_perturbation_push: Create a perturbation notification by applying transformations.
- _apply_perturbation: Apply perturbation to a feature and check if prediction changes.
- _check_after_perturbation: Check if perturbation changed the model's prediction.

"""
from typing import Optional

import numpy as np
import pandas as pd
from xxhash import xxh3_128_hexdigest

from giskard.core.core import SupportedModelTypes
from giskard.datasets.base import Dataset
from giskard.ml_worker.testing.functions.transformation import (
    compute_mad,
    mad_transformation,
)
from giskard.models.base.model import BaseModel
from giskard.push.utils import (
    SupportedPerturbationType,
    TransformationInfo,
    coltype_to_supported_perturbation_type,
)
from giskard.scanner.robustness.text_transformations import (
    TextGenderTransformation,
    TextLowercase,
    TextPunctuationRemovalTransformation,
    TextTitleCase,
    TextTypoTransformation,
    TextUppercase,
)
from ..push import PerturbationPush

text_transfo_list = [
    TextLowercase,
    TextUppercase,
    TextTitleCase,
    TextTypoTransformation,
    TextPunctuationRemovalTransformation,
    TextGenderTransformation,
]

hashed_typo_transformations = dict()


def create_perturbation_push(
    model: BaseModel, ds: Dataset, df: pd.DataFrame
) -> PerturbationPush:
    """Create a perturbation notification by applying transformations.

    Applies supported perturbations to each feature in the dataset
    based on column type. If the prediction changes after perturbation,
    creates and returns a PerturbationPush.

    Args:
        model: Model used for prediction
        ds: Dataset
        df: DataFrame containing row to analyze

    Returns:
        PerturbationPush if perturbation changed prediction, else None
    """

    for feat, coltype in ds.column_types.items():
        coltype = coltype_to_supported_perturbation_type(coltype)
        transformation_info = _apply_perturbation(model, ds, df, feat, coltype)
        value = df.iloc[0][feat]
        if transformation_info is not None:
            return PerturbationPush(
                feature=feat,
                value=value,
                transformation_info=transformation_info,
            )


def _apply_perturbation(
    model: BaseModel,
    ds: Dataset,
    df: pd.DataFrame,
    feature: str,
    col_type: SupportedPerturbationType,
) -> Optional[TransformationInfo]:
    """
    Apply perturbation to a feature and check if prediction changes.

    Creates a slice of the input dataframe with only the row to perturb.
    Applies supported perturbations based on column type.

    For numeric columns, adds/subtracts values based on mean absolute deviation.
    For text columns, applies predefined text transformations.

    After each perturbation, checks if the model's prediction changes
    compared to the original unperturbed input.

    Args:
        model (BaseModel): ML model to make predictions
        ds (Dataset): Original dataset
        df (pd.Dataframe): DataFrame containing row to perturb
        feature (str): Name of feature column to perturb
        col_type: Data type of feature column

    Returns:
        TransformationInfo if perturbation changed prediction, else None.
        Includes details like perturbed values, functions.
    """
    transformation_function = list()
    value_perturbed = list()
    transformation_functions_params = list()

    passed = False
    # Create a slice of the dataset with only the row to perturb
    ds_slice = Dataset(
        df=df,
        target=ds.target,
        column_types=ds.column_types.copy(),
        validation=False,
    )

    # Create a copy of the slice to apply the transformation
    ds_slice_copy = ds_slice.copy()

    # Apply the transformation
    if col_type == SupportedPerturbationType.NUMERIC:
        passed = _numeric(
            ds,
            ds_slice,
            ds_slice_copy,
            feature,
            model,
            transformation_function,
            transformation_functions_params,
            value_perturbed,
        )

    elif col_type == SupportedPerturbationType.TEXT:
        passed = _text(
            ds_slice,
            ds_slice_copy,
            feature,
            model,
            transformation_function,
            value_perturbed,
        )

    value_perturbed.reverse()
    transformation_function.reverse()
    transformation_functions_params.reverse()
    return (
        TransformationInfo(
            value_perturbed=value_perturbed,
            transformation_functions=transformation_function,
            transformation_functions_params=transformation_functions_params,
        )
        if passed
        else None
    )


def _text(
    ds_slice,
    ds_slice_copy,
    feature,
    model,
    transformation_function,
    value_perturbed,
):          
    passed = False
    # Iterate over the possible text transformations
    for text_transformation in text_transfo_list:
        # Create the transformation
        _is_typo_transformation = issubclass(text_transformation, TextTypoTransformation)
        kwargs = {}
        if _is_typo_transformation:
            kwargs = {"rng_seed": 1241}

        t = text_transformation(column=feature, **kwargs)

        # Transform the slice
        if _is_typo_transformation:
            _hash = xxh3_128_hexdigest(
                f"{', '.join(map(lambda x: repr(x), ds_slice_copy.df.values))}".encode("utf-8")
            )
            if _hash not in hashed_typo_transformations.keys():
                hashed_typo_transformations.update({_hash: ds_slice_copy.transform(t)})
            transformed = hashed_typo_transformations.get(_hash)
        else:
            transformed = ds_slice_copy.transform(t)

        # Generate the perturbation
        passed = _check_after_perturbation(model, ds_slice, transformed)

        if passed:
            value_perturbed.append(transformed.df[feature].values.item(0))
            transformation_function.append(t)
    if len(value_perturbed) > 0:
        passed = True
    return passed


def _numeric(
    ds: Dataset,
    ds_slice,
    ds_slice_copy,
    feature,
    model,
    transformation_function,
    transformation_functions_params,
    value_perturbed,
):
    # Compute the MAD of the column
    mad = compute_mad(ds.df[feature])  # Small issue: distribution might not be normal
    values_added_list = [
        np.linspace(-2 * mad, 0, num=10),
        np.linspace(2 * mad, 0, num=10),
    ]
    if ds.df.dtypes[feature] == "int64":
        values_added_list = [
            np.unique(np.linspace(-2 * mad, 0, num=10).round().astype(int)),
            np.unique(np.linspace(2 * mad, 0, num=10).round().astype(int)),
        ]
    value_to_perturb = ds.df[feature].iloc[0]
    for values_added in values_added_list:
        for value in values_added:
            if ds.df[feature].max() >= value + value_to_perturb >= ds.df[feature].min():
                # Create the transformation
                t = mad_transformation(column_name=feature, value_added=value)

                # Transform the slice
                transformed = ds_slice_copy.transform(t)

                # Generate the perturbation
                perturbed = _check_after_perturbation(model, ds_slice, transformed)

                if perturbed:
                    value_perturbed.append(transformed.df[feature].values.item(0))
                    transformation_function.append(t)
                    transformation_functions_params.append(
                        dict(column_name=feature, value_added=float(value))
                    )
                else:
                    break
    return len(transformation_function) > 0


def _check_after_perturbation(
    model: BaseModel, ref_row: Dataset, row_perturbed: Dataset
) -> bool:
    """
    Check if perturbation changed the model's prediction.

    Compares the model's prediction on the original unperturbed
    row versus the perturbed row.

    For classification, checks if predicted class changes.
    For regression, checks if prediction value changes significantly.

    Args:
        model (BaseModel): ML model
        ref_row (Dataset): Row before perturbation
        row_perturbed (Dataset): Row after perturbation

    Returns:
        bool indicating if prediction changed
    """
    if model.meta.model_type == SupportedModelTypes.CLASSIFICATION:
        # Compute the probability of the reference row
        ref_pred = model.predict(ref_row).prediction[0]
        # Compute the probability of the perturbed row
        pred = model.predict(row_perturbed).prediction[0]
        # Check if the probability of the reference row is different from the probability of the perturbed row
        passed = ref_pred != pred
        return passed

    elif model.meta.model_type == SupportedModelTypes.REGRESSION:
        # Compute the prediction of the reference row
        ref_val = model.predict(ref_row).prediction[0]
        # Compute the prediction of the perturbed row
        new_val = model.predict(row_perturbed).prediction[0]
        # Check if the prediction of the reference row is different from the prediction of the perturbed row
        passed = (new_val - ref_val) / ref_val >= 0.2
        return passed
