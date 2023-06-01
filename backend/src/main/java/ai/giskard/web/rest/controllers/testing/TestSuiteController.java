package ai.giskard.web.rest.controllers.testing;

import ai.giskard.domain.ml.TestSuite;
import ai.giskard.domain.ml.TestSuiteNew;
import ai.giskard.domain.ml.testing.Test;
import ai.giskard.repository.ml.*;
import ai.giskard.service.TestFunctionService;
import ai.giskard.repository.ml.DatasetRepository;
import ai.giskard.repository.ml.ModelRepository;
import ai.giskard.repository.ml.TestSuiteRepository;
import ai.giskard.service.TestService;
import ai.giskard.service.TestSuiteExecutionService;
import ai.giskard.service.TestSuiteService;
import ai.giskard.web.dto.GenerateTestSuiteDTO;
import ai.giskard.web.dto.SuiteTestDTO;
import ai.giskard.web.dto.TestSuiteCompleteDTO;
import ai.giskard.web.dto.TestSuiteDTO;
import ai.giskard.web.dto.mapper.GiskardMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;
import javax.validation.constraints.NotBlank;
import javax.validation.constraints.NotNull;
import java.util.List;
import java.util.Map;
import java.util.UUID;


@RestController
@RequestMapping("/api/v2/testing/")
@RequiredArgsConstructor
public class TestSuiteController {
    private final TestSuiteService testSuiteService;
    private final TestService testService;
    private final GiskardMapper giskardMapper;
    private final TestSuiteRepository testSuiteRepository;
    private final DatasetRepository datasetRepository;
    private final ModelRepository modelRepository;
    private final TestSuiteExecutionService testSuiteExecutionService;
    private final TestFunctionService testFunctionService;


    @PostMapping("project/{projectKey}/suites")
    @PreAuthorize("@permissionEvaluator.canWriteProjectKey(#projectKey)")
    @Transactional
    public Long saveTestSuite(@PathVariable("projectKey") @NotNull String projectKey, @Valid @RequestBody TestSuiteDTO dto) {
        TestSuite savedSuite = testSuiteRepository.save(giskardMapper.fromDTO(dto));
        return savedSuite.getId();
    }

    @PostMapping("project/{projectKey}/suites/generate")
    @PreAuthorize("@permissionEvaluator.canWriteProjectKey(#projectKey)")
    @Transactional
    public Long generateTestSuite(@PathVariable("projectKey") @NotNull String projectKey,
                                  @Valid @RequestBody GenerateTestSuiteDTO dto) {
        return testSuiteService.generateTestSuite(projectKey, dto);
    }

    @GetMapping("project/{projectId}/suites")
    @PreAuthorize("@permissionEvaluator.canReadProject(#projectId)")
    @Transactional
    public List<TestSuiteDTO> listTestSuites(@PathVariable("projectId") @NotNull Long projectId) {
        return giskardMapper.toDTO(testSuiteRepository.findAllByProjectId(projectId));
    }

    @GetMapping("project/{projectId}/suite/{suiteId}")
    @PreAuthorize("@permissionEvaluator.canReadProject(#projectId)")
    @Transactional
    public TestSuiteDTO listTestSuiteComplete(@PathVariable("projectId") @NotNull Long projectId,
                                              @PathVariable("suiteId") @NotNull Long suiteId) {
        return giskardMapper.toDTO(testSuiteRepository.findOneByProjectIdAndId(projectId, suiteId));
    }

    @GetMapping("project/{projectId}/suite/{suiteId}/complete")
    @PreAuthorize("@permissionEvaluator.canReadProject(#projectId)")
    @Transactional(readOnly = true)
    public TestSuiteCompleteDTO listTestSuite(@PathVariable("projectId") @NotNull Long projectId,
                                              @PathVariable("suiteId") @NotNull Long suiteId) {
        return new TestSuiteCompleteDTO(
            giskardMapper.toDTO(testSuiteRepository.findOneByProjectIdAndId(projectId, suiteId)),
            testFunctionService.findAll(),
            giskardMapper.datasetsToDatasetDTOs(datasetRepository.findAllByProjectId(projectId)),
            giskardMapper.modelsToModelDTOs(modelRepository.findAllByProjectId(projectId)),
            testSuiteExecutionService.listAllExecution(suiteId),
            testSuiteService.getSuiteInputs(projectId, suiteId)
        );
    }

    @PostMapping("project/{projectId}/suite/{suiteId}/test")
    @PreAuthorize("@permissionEvaluator.canWriteProject(#projectId)")
    @Transactional
    public TestSuiteDTO addTestToSuite(@PathVariable("projectId") long projectId,
                                          @PathVariable("suiteId") long suiteId,
                                          @Valid @RequestBody SuiteTestDTO suiteTest) {
        return giskardMapper.toDTO(testSuiteService.addTestToSuite(suiteId, suiteTest));
    }

    @PostMapping("project/{projectId}/suite/{suiteId}/schedule-execution")
    @PreAuthorize("@permissionEvaluator.canReadProject(#projectId)")
    @Transactional
    public UUID scheduleTestSuiteExecution(@PathVariable("projectId") @NotNull Long projectId,
                                           @PathVariable("suiteId") @NotNull Long suiteId,
                                           @Valid @RequestBody Map<@NotBlank String, @NotNull String> inputs) {
        return testSuiteService.scheduleTestSuiteExecution(projectId, suiteId, inputs);
    }

    @PutMapping("project/{projectId}/suite/{suiteId}/test/{testUuid}/inputs")
    @PreAuthorize("@permissionEvaluator.canWriteProject(#projectId)")
    @Transactional
    public TestSuiteDTO updateTestInputs(@PathVariable("projectId") long projectId,
                                         @PathVariable("suiteId") long suiteId,
                                         @PathVariable("testUuid") @NotBlank String testUuid,
                                         @Valid @RequestBody Map<@NotBlank String, @NotNull String> inputs) {
        return testSuiteService.updateTestInputs(suiteId, testUuid, inputs);
    }

}
