import { ConnectorConfig, DataConnect, QueryRef, QueryPromise, MutationRef, MutationPromise } from 'firebase/data-connect';

export const connectorConfig: ConnectorConfig;

export type TimestampString = string;
export type UUIDString = string;
export type Int64String = string;
export type DateString = string;




export interface CreateExperienceData {
  experience_insert: Experience_Key;
}

export interface CreateExperienceVariables {
  company: string;
  jobTitle: string;
  startDate: DateString;
  userId: UUIDString;
}

export interface CreateUserData {
  user_insert: User_Key;
}

export interface Experience_Key {
  id: UUIDString;
  __typename?: 'Experience_Key';
}

export interface GetUserByIdData {
  user?: {
    id: UUIDString;
    displayName: string;
    email: string;
    bio?: string | null;
    photoUrl?: string | null;
    createdAt: TimestampString;
  } & User_Key;
}

export interface GetUserByIdVariables {
  id: UUIDString;
}

export interface Goal_Key {
  id: UUIDString;
  __typename?: 'Goal_Key';
}

export interface ListExperiencesByUserData {
  experiences: ({
    id: UUIDString;
    company: string;
    jobTitle: string;
    startDate: DateString;
    endDate?: DateString | null;
    description?: string | null;
  } & Experience_Key)[];
}

export interface ListExperiencesByUserVariables {
  userId: UUIDString;
}

export interface Project_Key {
  id: UUIDString;
  __typename?: 'Project_Key';
}

export interface Skill_Key {
  id: UUIDString;
  __typename?: 'Skill_Key';
}

export interface User_Key {
  id: UUIDString;
  __typename?: 'User_Key';
}

interface CreateUserRef {
  /* Allow users to create refs without passing in DataConnect */
  (): MutationRef<CreateUserData, undefined>;
  /* Allow users to pass in custom DataConnect instances */
  (dc: DataConnect): MutationRef<CreateUserData, undefined>;
  operationName: string;
}
export const createUserRef: CreateUserRef;

export function createUser(): MutationPromise<CreateUserData, undefined>;
export function createUser(dc: DataConnect): MutationPromise<CreateUserData, undefined>;

interface GetUserByIdRef {
  /* Allow users to create refs without passing in DataConnect */
  (vars: GetUserByIdVariables): QueryRef<GetUserByIdData, GetUserByIdVariables>;
  /* Allow users to pass in custom DataConnect instances */
  (dc: DataConnect, vars: GetUserByIdVariables): QueryRef<GetUserByIdData, GetUserByIdVariables>;
  operationName: string;
}
export const getUserByIdRef: GetUserByIdRef;

export function getUserById(vars: GetUserByIdVariables): QueryPromise<GetUserByIdData, GetUserByIdVariables>;
export function getUserById(dc: DataConnect, vars: GetUserByIdVariables): QueryPromise<GetUserByIdData, GetUserByIdVariables>;

interface CreateExperienceRef {
  /* Allow users to create refs without passing in DataConnect */
  (vars: CreateExperienceVariables): MutationRef<CreateExperienceData, CreateExperienceVariables>;
  /* Allow users to pass in custom DataConnect instances */
  (dc: DataConnect, vars: CreateExperienceVariables): MutationRef<CreateExperienceData, CreateExperienceVariables>;
  operationName: string;
}
export const createExperienceRef: CreateExperienceRef;

export function createExperience(vars: CreateExperienceVariables): MutationPromise<CreateExperienceData, CreateExperienceVariables>;
export function createExperience(dc: DataConnect, vars: CreateExperienceVariables): MutationPromise<CreateExperienceData, CreateExperienceVariables>;

interface ListExperiencesByUserRef {
  /* Allow users to create refs without passing in DataConnect */
  (vars: ListExperiencesByUserVariables): QueryRef<ListExperiencesByUserData, ListExperiencesByUserVariables>;
  /* Allow users to pass in custom DataConnect instances */
  (dc: DataConnect, vars: ListExperiencesByUserVariables): QueryRef<ListExperiencesByUserData, ListExperiencesByUserVariables>;
  operationName: string;
}
export const listExperiencesByUserRef: ListExperiencesByUserRef;

export function listExperiencesByUser(vars: ListExperiencesByUserVariables): QueryPromise<ListExperiencesByUserData, ListExperiencesByUserVariables>;
export function listExperiencesByUser(dc: DataConnect, vars: ListExperiencesByUserVariables): QueryPromise<ListExperiencesByUserData, ListExperiencesByUserVariables>;

