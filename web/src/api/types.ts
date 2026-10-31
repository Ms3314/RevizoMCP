// API contract mirrored from server/app/service.py + models.py.
// Kept in sync by hand; the server is the source of truth.

export type Difficulty = "easy" | "medium" | "hard";

export interface Problem {
  problem_id: string;
  problem_link: string;
  difficulty: Difficulty;
  problem_description: string;
  topics: string[];
  solved: boolean;
  last_solved: string | null; // ISO date
  interval_days: number;
  repetitions: number;
  mistakes: string;
  watch_out?: string | null;
}

export interface Attempt {
  date: string;
  solved: boolean;
  mistakes: string;
  tags: string[];
}

export interface Stats {
  total: number;
  solved: number;
  backlog: number;
  due_today: number;
  by_difficulty: { easy: number; medium: number; hard: number };
}

export interface DueCard {
  p: Problem;
  watch_out?: string | null;
  when: string; // "never attempted" | "Xd overdue" | "due today"
}

export interface WeakPoint {
  tag: string;
  count: number;
  last_seen: string;
  recent_problems: string[];
  pct: number;
}

export interface DashboardRow {
  p: Problem;
  due: boolean;
  history: Attempt[];
}

export interface DashboardData {
  stats: Stats;
  due: DueCard[];
  weak_points: WeakPoint[];
  rows: DashboardRow[];
  today_long: string;
  filters: { difficulty: string; status: string; topic: string };
}

export interface SessionUser {
  id: number;
  email: string;
  display_name: string;
}

export interface LeetCodeStatus {
  connected: boolean;
  username: string;
  notice?: string | null;
}

export interface LeetCodeImportResult {
  imported?: number;
  duplicates?: number;
  failed?: string[];
  [key: string]: unknown;
}

// CSV import SSE events
export interface ImportStart {
  type: "start";
  total: number;
  skipped: number;
}
export interface ImportProgress {
  type: "progress";
  processed: number;
  total: number;
  imported: number;
  duplicates: number;
}
export interface ImportDone {
  type: "done";
  imported: number;
  duplicates: number;
  skipped: { row_number: number; reason: string }[];
  extras_ignored: string[];
  too_many_rows: boolean;
  failed: string[];
}
export type ImportEvent = ImportStart | ImportProgress | ImportDone;

// Study plan + streak
export interface DayStreak {
  date: string;
  count: number;
}

export interface Streak {
  current: number;
  longest: number;
  days: DayStreak[];
}

export interface StudyPlanSettings {
  revisions_per_session: number;
  backlog_per_session: number;
}

export interface ProblemSuggestion {
  problem_id: string;
  problem_link: string;
  difficulty: string;
  problem_description: string;
  topics: string[];
  solved: boolean;
  last_solved: string | null;
  interval_days: number;
  repetitions: number;
  mistakes: string;
  watch_out: string | null;
}

export interface StudyPlan {
  settings: StudyPlanSettings;
  old_target: number;
  old_solved_today: number;
  new_target: number;
  new_solved_today: number;
  old_suggestions: ProblemSuggestion[];
  new_suggestions: ProblemSuggestion[];
  weak_topics: string[];
  streak: Streak;
}

export interface SolveIn {
  solved?: boolean;
  mistakes?: string | null;
  mistake_tags?: string[] | null;
}
