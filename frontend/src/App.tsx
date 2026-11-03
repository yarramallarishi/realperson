import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowUpRight, Bot, Check, ChevronDown, ChevronRight,
  CircleHelp, Command, Gauge, LogOut, Menu, MessageSquareText, Radio, Server,
  Settings2, Shield, Sparkles, Users, X,
} from "lucide-react";
import { Analytics, api, avatarUrl, Guild, guildIconUrl, Settings, User } from "./api";
import ActivityChart from "./ActivityChart";

type Section = "overview" | "ai" | "automod" | "welcome";
type Notice = { kind: "success" | "error"; text: string };

const sectionInfo: Record<Section, { title: string; subtitle: string; icon: typeof Gauge }> = {
  overview: { title: "Overview", subtitle: "Your server, at a glance.", icon: Gauge },
  ai: { title: "AI assistant", subtitle: "Shape how OmniBot joins the conversation.", icon: Sparkles },
  automod: { title: "Auto moderation", subtitle: "Keep conversations welcoming and on-topic.", icon: Shield },
  welcome: { title: "Welcome messages", subtitle: "Give every new member a thoughtful hello.", icon: MessageSquareText },
};

const number = (value: number) => new Intl.NumberFormat("en").format(value);

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [guilds, setGuilds] = useState<Guild[]>([]);
  const [guildId, setGuildId] = useState("");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [section, setSection] = useState<Section>("overview");
  const [notice, setNotice] = useState<Notice | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [guildMenuOpen, setGuildMenuOpen] = useState(false);
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState("");

  const selectedGuild = useMemo(() => guilds.find((guild) => guild.id === guildId), [guilds, guildId]);

  const loadGuildData = useCallback(async (id: string) => {
    const [config, stats] = await Promise.all([
      api<Settings>(`/api/guilds/${id}/config`),
      api<Analytics>(`/api/guilds/${id}/analytics`),
    ]);
    setSettings(config);
    setAnalytics(stats);
  }, []);

  useEffect(() => {
    let active = true;
    async function initialize() {
      try {
        const [currentUser, servers] = await Promise.all([
          api<User>("/api/me"),
          api<Guild[]>("/api/guilds"),
        ]);
        if (!active) return;
        setUser(currentUser);
        setGuilds(servers);
        if (servers.length) {
          setGuildId(servers[0].id);
        }
      } catch {
        if (active) setUser(null);
      } finally {
        if (active) setLoading(false);
      }
    }
    void initialize();
    return () => { active = false; };
  }, [loadGuildData]);

  useEffect(() => {
    if (!guildId || !user) return;
    setDataLoading(true);
    setDataError("");
    setSettings(null);
    setAnalytics(null);
    void loadGuildData(guildId)
      .catch((error: Error) => setDataError(error.message))
      .finally(() => setDataLoading(false));
  }, [guildId, user, loadGuildData]);

  const saveSection = async (target: Exclude<Section, "overview">, values: object) => {
    if (!guildId) return;
    setSaving(true);
    setNotice(null);
    try {
      const saved = await api<Settings[typeof target]>(`/api/guilds/${guildId}/config/${target}`, {
        method: "PATCH",
        body: JSON.stringify({ values }),
      });
      setSettings((current) => current ? { ...current, [target]: { ...current[target], ...saved } } : current);
      setNotice({ kind: "success", text: "Changes saved successfully." });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Could not save your changes." });
    } finally {
      setSaving(false);
    }
  };

  const logout = async () => {
    try {
      await api<{ ok: boolean }>("/auth/logout", { method: "POST" });
      setUser(null);
      setGuilds([]);
      setGuildId("");
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Sign out failed." });
    }
  };

  if (loading) return <LoadingScreen />;
  if (!user) return <LoginScreen />;

  const nav = (
    <>
      <div className="nav-label">WORKSPACE</div>
      {(Object.keys(sectionInfo) as Section[]).map((key) => {
        const item = sectionInfo[key];
        const Icon = item.icon;
        return (
          <button key={key} className={`nav-item ${section === key ? "active" : ""}`}
            onClick={() => { setSection(key); setMenuOpen(false); }}>
            <Icon size={17} strokeWidth={1.8} /><span>{item.title}</span>
            {section === key && <span className="nav-active-dot" />}
          </button>
        );
      })}
      <div className="nav-label nav-label-spaced">RESOURCES</div>
      <a className="nav-item nav-link" href="https://discord.com/developers/docs" target="_blank" rel="noreferrer">
        <CircleHelp size={17} strokeWidth={1.8} /><span>Help center</span><ArrowUpRight size={14} className="nav-external" />
      </a>
      <div className="sidebar-bottom">
        <div className="bot-status"><span className="status-pulse" /><div><strong>All systems normal</strong><small>OmniBot is ready</small></div></div>
        <button className="user-card" onClick={() => void logout()}>
          {avatarUrl(user) ? <img src={avatarUrl(user)!} alt="" /> : <span className="avatar-fallback">{user.username[0]?.toUpperCase()}</span>}
          <span className="user-name"><strong>{user.global_name || user.username}</strong><small>Discord account</small></span>
          <LogOut size={15} className="logout-icon" />
        </button>
      </div>
    </>
  );

  return (
    <div className="app-shell">
      {menuOpen && <button aria-label="Close menu" className="mobile-backdrop" onClick={() => setMenuOpen(false)} />}
      <aside className={`sidebar ${menuOpen ? "sidebar-open" : ""}`}>
        <div className="brand"><div className="brand-mark"><Bot size={21} /></div><span>omni<span className="brand-light">bot</span></span><span className="brand-badge">BETA</span></div>
        <button className="workspace-switch" onClick={() => setGuildMenuOpen((open) => !open)}>
          <div className="workspace-icon">{selectedGuild?.icon && guildIconUrl(selectedGuild)
            ? <img src={guildIconUrl(selectedGuild)!} alt="" />
            : <Server size={17} />}</div>
          <div className="workspace-copy"><small>MANAGING SERVER</small><strong>{selectedGuild?.name ?? "Select a server"}</strong></div>
          <ChevronDown size={16} className={guildMenuOpen ? "rotate" : ""} />
        </button>
        {guildMenuOpen && (
          <div className="guild-popover">
            {guilds.map((guild) => <button key={guild.id} onClick={() => { setGuildId(guild.id); setGuildMenuOpen(false); }}>
              {guildIconUrl(guild) ? <img src={guildIconUrl(guild)!} alt="" /> : <Server size={15} />}
              <span>{guild.name}</span>{guild.id === guildId && <Check size={15} />}
            </button>)}
            {!guilds.length && <p>No manageable servers found.</p>}
          </div>
        )}
        <nav className="navigation">{nav}</nav>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <button aria-label="Open menu" className="mobile-menu" onClick={() => setMenuOpen(true)}><Menu size={20} /></button>
          <div className="breadcrumbs"><span>Workspace</span><ChevronRight size={14} /><strong>{sectionInfo[section].title}</strong></div>
          <div className="topbar-right">
            <span className="live-pill"><span /> LIVE</span>
            <span className="topbar-divider" />
            <span className="topbar-server">{selectedGuild?.name}</span>
          </div>
        </header>
        <div className="page-content">
          {notice && <div className={`notice ${notice.kind}`} role="status">{notice.kind === "success" ? <Check size={16} /> : <X size={16} />}{notice.text}<button onClick={() => setNotice(null)} aria-label="Dismiss"><X size={15} /></button></div>}
          {!guilds.length ? <EmptyServers /> : dataError ? <div className="empty-state"><div className="empty-icon"><Activity size={22} /></div><h2>Couldn't load this server</h2><p>{dataError}</p><button className="save-button" onClick={() => { setDataError(""); setDataLoading(true); void loadGuildData(guildId).catch((error: Error) => setDataError(error.message)).finally(() => setDataLoading(false)); }}>Try again <ArrowUpRight size={14} /></button></div> : dataLoading || !settings || !analytics ? <PageLoading /> : (
            <div className="page-enter">
              <div className="page-heading">
                <div><div className="eyebrow"><span className="eyebrow-line" /> SERVER CONTROL CENTER</div><h1>{sectionInfo[section].title}</h1><p>{sectionInfo[section].subtitle}</p></div>
                <div className="heading-server">
                  <span className="server-avatar">{selectedGuild?.icon && guildIconUrl(selectedGuild) ? <img src={guildIconUrl(selectedGuild)!} alt="" /> : <Server size={18} />}</span>
                  <span><small>CONFIGURING</small><strong>{selectedGuild?.name}</strong></span>
                </div>
              </div>
              {section === "overview" && <Overview analytics={analytics} settings={settings} setSection={setSection} />}
              {section === "ai" && <AISettings settings={settings} save={saveSection} saving={saving} />}
              {section === "automod" && <AutomodSettings settings={settings} save={saveSection} saving={saving} />}
              {section === "welcome" && <WelcomeSettings settings={settings} save={saveSection} saving={saving} />}
            </div>
          )}
          <footer className="footer"><span>OmniBot <b>·</b> Server operations, made clear.</span><span>Built for communities <span className="footer-heart">✦</span></span></footer>
        </div>
      </main>
    </div>
  );
}

function LoadingScreen() {
  return <div className="loading-screen"><div className="brand-mark"><Bot size={22} /></div><div className="loading-line" /><p>Waking up your workspace...</p></div>;
}

function LoginScreen() {
  return <main className="login-screen">
    <div className="login-glow glow-one" /><div className="login-glow glow-two" />
    <div className="login-brand"><div className="brand-mark"><Bot size={22} /></div><span>omni<span className="brand-light">bot</span></span></div>
    <div className="login-card">
      <div className="login-icon"><Sparkles size={22} /></div>
      <div className="eyebrow"><span className="eyebrow-line" /> YOUR COMMUNITY, IN SYNC</div>
      <h1>Good servers<br />run <span>on purpose.</span></h1>
      <p>One calm control center for the people, conversations, and little moments that make your server yours.</p>
      <a className="discord-login" href="/auth/login"><DiscordIcon /><span>Continue with Discord</span><ArrowUpRight size={16} /></a>
      <div className="login-note"><Shield size={14} /> We only see servers you can manage.</div>
    </div>
    <div className="login-footer"><span>OMNIBOT DASHBOARD</span><span>Thoughtful tools for thriving communities</span></div>
  </main>;
}

function DiscordIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true" className="discord-icon"><path fill="currentColor" d="M19.7 5.3A19.2 19.2 0 0 0 15 3.8l-.6 1.2a17.7 17.7 0 0 0-4.8 0L9 3.8a19.3 19.3 0 0 0-4.7 1.5C1.3 9.6.5 13.8.9 18a19.4 19.4 0 0 0 5.8 3l1.2-2a12.6 12.6 0 0 1-1.9-.9l.5-.4a13.8 13.8 0 0 0 11 0l.5.4a12 12 0 0 1-1.9.9l1.2 2a19.3 19.3 0 0 0 5.8-3c.5-4.9-.8-9-3.4-12.7ZM8.7 15.7c-1.1 0-2-1-2-2.2s.9-2.2 2-2.2 2.1 1 2 2.2c0 1.2-.9 2.2-2 2.2Zm6.6 0c-1.1 0-2-1-2-2.2s.9-2.2 2-2.2 2.1 1 2 2.2-.9 2.2-2 2.2Z" /></svg>;
}

function Overview({ analytics, settings, setSection }: {
  analytics: Analytics; settings: Settings; setSection: (section: Section) => void;
}) {
  const enabledModules = [settings.ai.enabled, settings.automod.enabled, settings.welcome.enabled].filter(Boolean).length;
  return <>
    <section className="welcome-banner">
      <div className="banner-orb orb-a" /><div className="banner-orb orb-b" />
      <div className="banner-content"><div className="banner-label"><span className="banner-dot" /> YOUR SERVER IS IN GOOD HANDS</div>
        <h2>Make room for<br /><em>the good stuff.</em></h2>
        <p>OmniBot is quietly keeping things moving. Tune your tools to make this space feel even more like yours.</p>
        <button className="banner-button" onClick={() => setSection("ai")}>Personalize your bot <ArrowUpRight size={15} /></button>
      </div>
      <div className="banner-art" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="art-core"><Bot size={47} strokeWidth={1.3} /></div><span className="art-spark spark-a">✦</span><span className="art-spark spark-b">✧</span><span className="art-spark spark-c">✦</span><div className="art-label">OMNI <b>ONLINE</b></div></div>
    </section>
    <div className="section-title-row"><div><h2>A little pulse check</h2><p>Activity across your server this week.</p></div><span className="period-chip"><Activity size={13} /> LAST 7 DAYS</span></div>
    <section className="stats-grid">
      <StatCard icon={Sparkles} label="AI conversations" value={number(analytics.ai_requests)} note="questions answered" accent="violet" />
      <StatCard icon={Shield} label="Mod actions" value={number(analytics.moderation_cases)} note="cases recorded" accent="blue" />
      <StatCard icon={Radio} label="Automations" value={number(analytics.events.automod ?? 0)} note="messages checked" accent="mint" />
      <StatCard icon={Command} label="Modules active" value={`${enabledModules} / 3`} note="server essentials" accent="amber" />
    </section>
    <section className="overview-lower">
      <div className="panel activity-panel">
        <div className="panel-heading"><div><h3>AI activity</h3><p>Daily conversations with your assistant</p></div><span className="chart-legend"><i /> Requests</span></div>
        <div className="chart-wrap">{analytics.ai_by_day.length ? <ActivityChart data={analytics.ai_by_day} /> : <div className="chart-empty"><div className="chart-empty-icon"><Activity size={18} /></div><strong>Your first conversation is a good place to start.</strong><span>AI activity will show up here once members begin chatting.</span><button onClick={() => setSection("ai")}>Set up AI assistant <ChevronRight size={14} /></button></div>}</div>
      </div>
      <div className="panel modules-panel">
        <div className="panel-heading"><div><h3>Your toolkit</h3><p>Tools currently looking after things</p></div><Settings2 size={17} className="panel-heading-icon" /></div>
        <ModuleRow icon={Sparkles} name="AI assistant" detail="Helpful, always on hand" enabled={settings.ai.enabled} onClick={() => setSection("ai")} />
        <ModuleRow icon={Shield} name="Auto moderation" detail="A little less noise" enabled={settings.automod.enabled} onClick={() => setSection("automod")} />
        <ModuleRow icon={Users} name="Welcome messages" detail="A warmer first hello" enabled={settings.welcome.enabled} onClick={() => setSection("welcome")} />
      </div>
    </section>
  </>;
}

function StatCard({ icon: Icon, label, value, note, accent }: {
  icon: typeof Gauge; label: string; value: string; note: string; accent: string;
}) {
  return <div className="stat-card"><div className={`stat-icon ${accent}`}><Icon size={17} strokeWidth={1.8} /></div><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-note">{note}</div><div className={`stat-decoration ${accent}`} /></div>;
}

function ModuleRow({ icon: Icon, name, detail, enabled, onClick }: {
  icon: typeof Gauge; name: string; detail: string; enabled: boolean; onClick: () => void;
}) {
  return <button className="module-row" onClick={onClick}><span className="module-icon"><Icon size={16} /></span><span className="module-copy"><strong>{name}</strong><small>{detail}</small></span><span className={`module-state ${enabled ? "is-on" : ""}`}><i />{enabled ? "On" : "Off"}</span><ChevronRight size={15} className="module-chevron" /></button>;
}

function Toggle({ checked, onChange, label, description }: {
  checked: boolean; onChange: (value: boolean) => void; label: string; description?: string;
}) {
  return <div className="setting-row"><div><strong>{label}</strong>{description && <p>{description}</p>}</div><button type="button" className={`toggle ${checked ? "checked" : ""}`} role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange(!checked)}><span /></button></div>;
}

function SaveButton({ saving, onClick }: { saving: boolean; onClick: () => void }) {
  return <button className="save-button" onClick={onClick} disabled={saving}>{saving ? <><span className="button-spinner" /> Saving changes</> : <><Check size={16} /> Save changes</>}</button>;
}

function AISettings({ settings, save, saving }: {
  settings: Settings; save: (section: "ai", values: object) => Promise<void>; saving: boolean;
}) {
  const [form, setForm] = useState(settings.ai);
  useEffect(() => setForm(settings.ai), [settings.ai]);
  return <section className="settings-layout">
    <div className="settings-main">
      <div className="panel settings-panel"><div className="settings-panel-heading"><span className="large-setting-icon violet"><Sparkles size={19} /></span><div><h2>Assistant presence</h2><p>Choose when OmniBot can lend a hand.</p></div></div>
        <Toggle checked={form.enabled} onChange={(enabled) => setForm({ ...form, enabled })} label="Enable AI assistant" description="Allow /ask and mention replies in this server." />
        <div className="form-field"><label htmlFor="ai-model">AI model</label><select id="ai-model" value={form.model} onChange={(event) => setForm({ ...form, model: event.target.value })}><option value="llama-3.3-70b-versatile">Llama 3.3 · 70B — balanced</option><option value="llama-3.1-8b-instant">Llama 3.1 · 8B — fast</option><option value="openai/gpt-oss-20b">GPT-OSS · 20B — reasoning</option></select><small>Responses are generated by Groq. Provider keys stay on the server.</small></div>
        <div className="form-grid"><div className="form-field"><label htmlFor="cooldown">User cooldown</label><div className="input-suffix"><input id="cooldown" type="number" min={1} max={120} value={form.cooldown_seconds} onChange={(event) => setForm({ ...form, cooldown_seconds: Number(event.target.value) })} /><span>seconds</span></div></div><div className="form-field"><label htmlFor="memory">Conversation memory</label><div className="input-suffix"><input id="memory" type="number" min={0} max={20} value={form.memory_messages} onChange={(event) => setForm({ ...form, memory_messages: Number(event.target.value) })} /><span>messages</span></div></div></div>
      </div>
      <div className="panel settings-panel"><div className="settings-panel-heading"><span className="large-setting-icon blue"><MessageSquareText size={19} /></span><div><h2>Personality</h2><p>Give your assistant a voice that fits here.</p></div></div>
        <div className="form-field"><label htmlFor="personality">System instructions</label><textarea id="personality" rows={5} maxLength={1200} value={form.personality} onChange={(event) => setForm({ ...form, personality: event.target.value })} /><div className="field-foot"><small>Keep instructions kind and clear. The assistant cannot run tools or take actions.</small><small>{form.personality.length}/1200</small></div></div>
      </div>
      <div className="save-row"><SaveButton saving={saving} onClick={() => void save("ai", form)} /></div>
    </div>
    <aside className="settings-aside"><div className="aside-card ai-aside"><div className="aside-orb"><Sparkles size={19} /></div><span className="aside-kicker">A NOTE ON AI</span><h3>Helpful by design.<br />Never in charge.</h3><p>OmniBot's assistant responds with text only. It can't run code, manage members, or take actions on anyone's behalf.</p></div><div className="aside-tip"><div className="tip-top"><span>GOOD TO KNOW</span><span className="tip-dot" /></div><p>Conversation memory is private to each member and channel. Use <code>/resetchat</code> to clear your own.</p></div></aside>
  </section>;
}

function AutomodSettings({ settings, save, saving }: {
  settings: Settings; save: (section: "automod", values: object) => Promise<void>; saving: boolean;
}) {
  const [form, setForm] = useState(settings.automod);
  const [wordsText, setWordsText] = useState(settings.automod.banned_words.join(", "));
  useEffect(() => { setForm(settings.automod); setWordsText(settings.automod.banned_words.join(", ")); }, [settings.automod]);
  return <section className="settings-layout">
    <div className="settings-main"><div className="panel settings-panel"><div className="settings-panel-heading"><span className="large-setting-icon blue"><Shield size={19} /></span><div><h2>Guardrails</h2><p>Choose which patterns OmniBot should catch.</p></div></div>
      <Toggle checked={form.enabled} onChange={(enabled) => setForm({ ...form, enabled })} label="Enable auto moderation" description="When off, OmniBot observes nothing and removes no messages." />
      <Toggle checked={form.duplicate_filter} onChange={(duplicate_filter) => setForm({ ...form, duplicate_filter })} label="Repeated messages" description="Remove the same message when a member repeats it within 12 seconds." />
      <Toggle checked={form.invite_filter} onChange={(invite_filter) => setForm({ ...form, invite_filter })} label="Discord invite links" description="Remove invite links from messages." />
      <div className="form-grid"><div className="form-field"><label htmlFor="mention-limit">Mention limit</label><div className="input-suffix"><input id="mention-limit" type="number" min={1} max={20} value={form.mention_limit} onChange={(event) => setForm({ ...form, mention_limit: Number(event.target.value) })} /><span>mentions</span></div></div><div className="form-field"><label htmlFor="caps-threshold">Caps threshold</label><div className="input-suffix"><input id="caps-threshold" type="number" min={0.5} max={1} step={0.05} value={form.caps_threshold} onChange={(event) => setForm({ ...form, caps_threshold: Number(event.target.value) })} /><span>0.5 – 1</span></div></div></div>
      <div className="form-field"><label htmlFor="banned-words">Banned words</label><input id="banned-words" type="text" value={wordsText} placeholder="word one, word two" onChange={(event) => { setWordsText(event.target.value); setForm({ ...form, banned_words: event.target.value.split(",").map((word) => word.trim()).filter(Boolean) }); }} /><small>Comma-separated. Matching is case-insensitive.</small></div>
      <div className="form-field"><label htmlFor="automod-log-channel">Moderation log channel ID</label><input id="automod-log-channel" type="text" inputMode="numeric" value={form.log_channel_id ?? ""} placeholder="Optional channel ID" onChange={(event) => setForm({ ...form, log_channel_id: event.target.value || null })} /><small>Auto moderation and moderation command cases are logged here when configured.</small></div>
    </div><div className="save-row"><SaveButton saving={saving} onClick={() => void save("automod", form)} /></div></div>
    <aside className="settings-aside"><div className="aside-card safety-aside"><div className="aside-orb"><Shield size={19} /></div><span className="aside-kicker">BUILT WITH CARE</span><h3>Your space,<br />your boundaries.</h3><p>Automod only removes messages when enabled. The bot needs Manage Messages in a channel to remove offending content.</p></div><div className="aside-tip"><div className="tip-top"><span>NO AUTO-PUNISHMENT</span><span className="tip-dot" /></div><p>Automod removes the flagged message and logs the event. It never bans or times out anyone automatically.</p></div></aside>
  </section>;
}

function WelcomeSettings({ settings, save, saving }: {
  settings: Settings; save: (section: "welcome", values: object) => Promise<void>; saving: boolean;
}) {
  const [form, setForm] = useState(settings.welcome);
  useEffect(() => setForm(settings.welcome), [settings.welcome]);
  return <section className="settings-layout"><div className="settings-main"><div className="panel settings-panel"><div className="settings-panel-heading"><span className="large-setting-icon mint"><Users size={19} /></span><div><h2>First impressions</h2><p>A small welcome can go a long way.</p></div></div>
    <Toggle checked={form.enabled} onChange={(enabled) => setForm({ ...form, enabled })} label="Enable welcome messages" description="Post a greeting when a member joins." />
    <div className="form-field"><label htmlFor="welcome-channel">Welcome channel ID</label><input id="welcome-channel" type="text" inputMode="numeric" value={form.channel_id ?? ""} placeholder="For example: 123456789012345678" onChange={(event) => setForm({ ...form, channel_id: event.target.value || null })} /><small>Copy the channel ID from Discord with Developer Mode enabled.</small></div>
    <div className="form-field"><label htmlFor="welcome-message">Your message</label><textarea id="welcome-message" rows={4} maxLength={1000} value={form.message} onChange={(event) => setForm({ ...form, message: event.target.value })} /><div className="field-foot"><small>Use <code>{"{user}"}</code> to mention the new member and <code>{"{server}"}</code> for your server name.</small><small>{form.message.length}/1000</small></div></div>
    <div className="preview-box"><span className="preview-label">PREVIEW</span><p>{form.message.replaceAll("{user}", "@new-member").replaceAll("{server}", "Your server")}</p></div>
  </div><div className="save-row"><SaveButton saving={saving} onClick={() => void save("welcome", form)} /></div></div><aside className="settings-aside"><div className="aside-card welcome-aside"><div className="aside-orb"><MessageSquareText size={19} /></div><span className="aside-kicker">MAKE IT YOURS</span><h3>New faces.<br />Warm welcomes.</h3><p>Messages are sent by the bot directly in your selected channel. Check its View Channel and Send Messages permissions.</p></div></aside></section>;
}

function EmptyServers() {
  return <div className="empty-state"><div className="empty-icon"><Server size={22} /></div><h2>No manageable servers yet</h2><p>Sign in with an account that owns a Discord server or has the Manage Server permission. If the bot is not in your server, invite it from your Developer Portal application.</p><a href="/auth/login">Try Discord sign in <ArrowUpRight size={15} /></a></div>;
}

function PageLoading() {
  return <div className="page-loading"><div className="skeleton skeleton-title" /><div className="skeleton skeleton-subtitle" /><div className="skeleton-grid">{[1, 2, 3].map((item) => <div className="skeleton skeleton-card" key={item} />)}</div></div>;
}

export default App;
