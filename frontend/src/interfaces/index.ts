export interface IUserProfileMinimal {
    id: number,
    user_id: string,
    display_name?: string
}

export enum FeatureFlags {
    Auth
}