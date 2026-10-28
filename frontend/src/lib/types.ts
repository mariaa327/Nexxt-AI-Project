/** Shared API types mirrored from the FastAPI schemas. */

export type AgentOutput = {
  answer: string;
  key_points: string[];
  follow_up_questions: string[];
};
