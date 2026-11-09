import { useEffect, useState } from 'react'
import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { BookOpenText, FolderOpen, History as HistoryIcon, Menu, MessagesSquare, Monitor, Moon, Sun, X } from 'lucide-react'
import { Modal } from './components'
import { defaultConfig, initialSessions } from './data'
import type { PracticeConfig, Session } from './data'
import Practice from './Practice'
import Materials from './Materials'
import History from './History'
import './App.css'

type Theme = 'system' | 'light' | 'dark'
function Workspace() {
  const navigate = useNavigate()
  const location = useLocation()
  const [theme, setTheme] = useState<Theme>(() => { try { const value = localStorage.getItem('ia-theme'); return value === 'dark' || value === 'light' ? value : 'system' } catch { return 'system' } })
  const [menuOpen, setMenuOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [config, setConfig] = useState<PracticeConfig>(defaultConfig)
  const [run, setRun] = useState(0)
  const [active, setActive] = useState(false)
  const [sessions, setSessions] = useState<Session[]>(initialSessions)
  const [toast, setToast] = useState('')
  useEffect(() => { if (theme === 'system') { document.documentElement.removeAttribute('data-theme'); localStorage.removeItem('ia-theme') } else { document.documentElement.dataset.theme = theme; localStorage.setItem('ia-theme', theme) } }, [theme])
  useEffect(() => { if (!toast) return; const timer = window.setTimeout(() => setToast(''), 3200); return () => window.clearTimeout(timer) }, [toast])
  const page = location.pathname.startsWith('/materials') ? '资料管理' : location.pathname.startsWith('/history') ? '历史记录' : '面试练习'
  function start(next: PracticeConfig) { setConfig(next); setRun(n => n + 1); setActive(true); navigate('/practice') }
  function finish(session: Session) { setSessions(items => [session, ...items]); setActive(false); navigate(`/history/${session.id}`); setToast('练习记录已保存到当前演示空间') }
  const nav = [ { to: '/practice', label: '面试练习', Icon: MessagesSquare }, { to: '/materials', label: '资料管理', Icon: FolderOpen }, { to: '/history', label: '历史记录', Icon: HistoryIcon } ]
  return <div className="app-shell">
    {menuOpen && <button className="nav-scrim" aria-label="关闭导航" onClick={() => setMenuOpen(false)} />}
    <aside className={`sidebar ${menuOpen ? 'is-open' : ''}`}>
      <div className="sidebar-top"><NavLink to="/practice" className="brand" onClick={() => setMenuOpen(false)}>面试练习</NavLink><button className="icon-button sidebar-close" aria-label="关闭导航" onClick={() => setMenuOpen(false)}><X size={18} /></button></div>
      <nav aria-label="主导航">{nav.map(({ to, label, Icon }) => <NavLink key={to} end={to !== '/history'} to={to} className={({ isActive }) => `nav-item ${isActive ? 'is-active' : ''}`} onClick={() => setMenuOpen(false)}><Icon size={18} aria-hidden="true" /><span>{label}</span>{to === '/history' && <span className="nav-count">{sessions.length}</span>}</NavLink>)}</nav>
      <div className="sidebar-bottom"><button className="nav-item nav-button" onClick={() => { setHelpOpen(true); setMenuOpen(false) }}><BookOpenText size={18} aria-hidden="true" />使用说明</button><div className="theme-control"><span>主题</span><div className="theme-options" role="group" aria-label="主题模式">{([{ value: 'system', Icon: Monitor, label: '跟随系统' }, { value: 'light', Icon: Sun, label: '浅色' }, { value: 'dark', Icon: Moon, label: '深色' }] as const).map(({ value, Icon, label }) => <button key={value} title={label} aria-label={label} aria-pressed={theme === value} className={theme === value ? 'is-active' : ''} onClick={() => setTheme(value)}><Icon size={16} /></button>)}</div></div></div>
    </aside>
    <div className="main-shell"><header className="topbar"><button className="icon-button mobile-menu" aria-label="打开导航" onClick={() => setMenuOpen(true)}><Menu size={20} /></button><span className="top-context">{page}</span><span className="top-spacer" /></header><Routes>
      <Route path="/" element={<Navigate to="/practice" replace />} />
      <Route path="/practice" element={null} />
      <Route path="/materials" element={null} />
      <Route path="/history" element={null} />
      <Route path="/history/:id" element={null} />
      <Route path="*" element={<Navigate to="/practice" replace />} />
    </Routes><div hidden={page !== '面试练习'}><Practice key={`${run}-${config.focus}`} config={config} active={active} onStart={start} onFinish={finish} notify={setToast} /></div><div hidden={page !== '资料管理'}><Materials notify={setToast} /></div><div hidden={page !== '历史记录'}><History sessions={sessions} onPractice={(focus) => { setConfig(c => ({ ...c, focus: focus ?? c.focus })); setActive(false); navigate('/practice') }} /></div></div>
    <Modal open={helpOpen} onOpenChange={setHelpOpen} title="使用说明"><div className="help-content"><p>在资料管理中准备岗位描述和学习资料，再到面试练习选择题型与难度。答完一组后可查看反馈、示范回答和资料来源。</p><p>练习记录和文件操作目前使用浏览器内的演示数据，刷新页面后会重置。</p></div></Modal>
    {toast && <div className="toast" role="status"><span>{toast}</span><button className="icon-button" aria-label="关闭提示" onClick={() => setToast('')}><X size={16} /></button></div>}
  </div>
}
export default function App() { return <BrowserRouter><Workspace /></BrowserRouter> }
