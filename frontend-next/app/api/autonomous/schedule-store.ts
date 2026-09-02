// In-memory persistent schedule store for autonomous blog generator
export interface BlogSettingsState {
  auto_publish: boolean;
  auto_generate: boolean;
  frequency: string;
  posts_per_day: number;
  daily_blog_target: number;
  blogs_generated_today: number;
  generation_interval_minutes: number;
  schedule_label: string;
  auto_topic_selection: boolean;
  next_blog_in_minutes: number;
  next_run_timestamp: number;
  niche: string;
  domain: string;
  language: string;
  updated_at: string;
}

export const sharedSchedule: BlogSettingsState = {
  auto_publish: true,
  auto_generate: true,
  frequency: "every_3_min",
  posts_per_day: 10,
  daily_blog_target: 10,
  blogs_generated_today: 1,
  generation_interval_minutes: 3,
  schedule_label: "Every 3 min",
  auto_topic_selection: true,
  next_blog_in_minutes: 3,
  next_run_timestamp: Date.now() + 3 * 60 * 1000,
  niche: "Personal Injury Law",
  domain: "accident.innovatcs.com",
  language: "en",
  updated_at: new Date().toISOString(),
};

export function updateSchedule(updates: Partial<BlogSettingsState>) {
  Object.assign(sharedSchedule, updates);
  if (updates.generation_interval_minutes) {
    sharedSchedule.next_run_timestamp = Date.now() + updates.generation_interval_minutes * 60 * 1000;
    sharedSchedule.next_blog_in_minutes = updates.generation_interval_minutes;
  }
  sharedSchedule.updated_at = new Date().toISOString();
  return sharedSchedule;
}

export function getSchedule() {
  const secondsLeft = Math.max(0, Math.floor((sharedSchedule.next_run_timestamp - Date.now()) / 1000));
  sharedSchedule.next_blog_in_minutes = Math.max(1, Math.ceil(secondsLeft / 60));
  return {
    ...sharedSchedule,
    next_blog_seconds: secondsLeft,
  };
}
