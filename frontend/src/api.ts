export type Guild = {
  id: string;
  name: string;
  icon: string | null;
  owner: boolean;
  permissions: string;
};

export type User = {
  id: string;
  username: string;
  global_name: string | null;
  avatar: string | null;
};

export type Settings = {
  ai: {
    enabled: boolean;
    model: string;
    personality: string;
    cooldown_seconds: number;
    memory_messages: number;
    allowed_channels: string[];
  };
  automod: {
    enabled: boolean;
    invite_filter: boolean;
    duplicate_filter: boolean;
    mention_limit: number;
    caps_threshold: number;
    banned_words: string[];
    log_channel_id: string | null;
  };
  welcome: {
    enabled: boolean;
    channel_id: string | null;
    message: string;
  };
  general: { prefix: string; timezone: string };
};

export type Analytics = {
  period_days: number;
  ai_requests: number;
  prompt_tokens: number;
  completion_tokens: number;
  moderation_cases: number;
  events: Record<string, number>;
  ai_by_day: { date: string; requests: number }[];
};

const API_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const avatarUrl = (user: User) =>
  user.avatar
    ? `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png?size=96`
    : null;

export const guildIconUrl = (guild: Guild) =>
  guild.icon ? `https://cdn.discordapp.com/icons/${guild.id}/${guild.icon}.png?size=96` : null;
