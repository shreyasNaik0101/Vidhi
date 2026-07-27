// Typed client for the Express API. Dates are ISO strings ('YYYY-MM-DD').

export type Status =
  | 'in_force'
  | 'not_yet_in_force'
  | 'no_longer_in_force'
  | 'no_provision';

export interface Entity {
  code: string;
  name: string;
}

export interface ClauseOption {
  clauseNumber: string;
  chapter: string | null;
}

export interface Version {
  mdFamily: string;
  entityCode: string;
  clauseNumber: string;
  chapter: string | null;
  text: string;
  validFrom: string;
  validTo: string | null;
  issuedDate?: string | null;
  sourceRef?: string | null;
}

export interface Resolution {
  status: Status;
  mdFamily: string;
  entityCode: string;
  clauseNumber: string;
  asOf: string;
  text: string | null;
  validFrom: string | null;
  validTo: string | null;
  effectiveDate: string | null;
  note: string | null;
  sourceRef?: string | null;
  issuedDate?: string | null;
  candidates: Version[];
}

export interface ChangeMember {
  entityCode: string;
  rbiRef: string;
  chapter: string | null;
  sectionHeading: string | null;
  similarity: number | null;
}

export interface ChangeGroup {
  id: number;
  label: string;
  issuedDate: string;
  effectiveDate: string | null;
  members: ChangeMember[];
}

export interface TimelineVersion {
  clauseNumber: string;
  chapter: string | null;
  text: string;
  validFrom: string;
  validTo: string | null;
  createdBy: string | null;
  supersededBy: string | null;
}

export interface GoldenScenario {
  id: string;
  category: string;
  question: string;
  entity: string;
  family: string;
  clause: string;
  asOf: string;
  expectedStatus: string;
  note: string;
}

export interface NaiveAnswer {
  text: string;
  answerEntity: string | null;
  effectiveDate: string | null;
  issuedDate: string | null;
  errors: { entity: boolean; temporal: boolean; shouldAbstain: boolean };
}

export interface CompareResult {
  scenario: { entity: string; family: string; clause: string; asOf: string; question: string };
  full: Resolution;
  naive: NaiveAnswer | null;
}

export interface AskResult {
  need?: 'entity' | 'date';
  message?: string;
  entity?: string;
  interpreted?: { entity: string; family: string; asOf: string; clause: string | null };
  answer?: Resolution;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  entities: () => get<Entity[]>('/api/entities'),
  clauses: (entity: string, family = 'IRACP') =>
    get<ClauseOption[]>(`/api/clauses?entity=${entity}&family=${family}`),
  resolve: (entity: string, clause: string, asOf: string, family = 'IRACP') =>
    get<Resolution>(
      `/api/resolve?entity=${entity}&family=${family}&clause=${clause}&as_of=${asOf}`,
    ),
  changes: () => get<ChangeGroup[]>('/api/changes'),
  timeline: (family: string, entity: string, clause: string) =>
    get<TimelineVersion[]>(`/api/clauses/${family}/${entity}/${clause}/timeline`),
  golden: () => get<GoldenScenario[]>('/api/golden'),
  ask: (q: string, family = 'IRACP') =>
    get<AskResult>(`/api/ask?q=${encodeURIComponent(q)}&family=${family}`),
  compare: (s: GoldenScenario) =>
    get<CompareResult>(
      `/api/compare?entity=${s.entity}&family=${s.family}&clause=${s.clause}` +
        `&as_of=${s.asOf}&question=${encodeURIComponent(s.question)}`,
    ),
};
