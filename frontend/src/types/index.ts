export type Role = "student" | "instructor" | "admin";

export interface User {
  id: number;
  email: string;
  name: string;
  role: Role;
  student_id: string;
  photo_url?: string;
}

export interface Tokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Citation {
  cid: string;
  label: string;
  source_type: string;
  locator: string;
  page?: number | null;
  slide?: number | null;
  timestamp?: number | null;
  link: string;
  resolvable: boolean;
}

export interface Evidence {
  rank?: number;
  resource_id: string;
  citation: string;
  source_type?: string;
  page?: number | null;
  timestamp?: number | null;
  confidence?: number;
  text: string;
}

export interface Answer {
  answer: string;
  confidence: number;
  grounding?: number | null;
  generator: string;
  citations: Citation[];
  evidence: Evidence[];
  reasoning: string[];
  used_web: boolean;
  needs_web: boolean;
  chat_id?: number | null;
}

export interface ChatSummary {
  id: number;
  title: string;
  updated_at: string;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  data?: Partial<Answer>;
}

export interface ResourceNode {
  resource_id: string;
  title: string;
  doc_type: string;
  topics?: string[];
}

export interface ModuleNode {
  module: string;
  resources: ResourceNode[];
}

export interface CourseNode {
  course: string;
  track: string;
  modules: ModuleNode[];
}

export interface KnowledgeTree {
  courses: CourseNode[];
}

export type QuizType = "multiple_choice" | "true_false" | "short_answer";

export interface QuizQuestion {
  type: QuizType;
  question: string;
  options: string[];
  answer: string;
  explanation: string;
  difficulty: string;
}

export interface Quiz {
  concept: string;
  label: string;
  difficulty: string;
  source: string;
  questions: QuizQuestion[];
}

export interface StudentProfile {
  summary: {
    overall_mastery: number;
    n_tracked: number;
    n_weak: number;
    n_strong: number;
    n_events: number;
  };
  weak: { concept: string; mastery: number }[];
  strong: { concept: string; mastery: number }[];
  profile: Record<string, unknown>;
}
