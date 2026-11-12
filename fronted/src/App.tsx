import { useEffect, useState } from 'react'
import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { BookOpenText, FolderOpen, History as HistoryIcon, ListChecks, Menu, MessagesSquare, Monitor, Moon, Sun, X } from 'lucide-react'
import { Modal } from './components'
import { initialSessions } from './data'
import MockInterview from './MockInterview'
import Materials from './Materials'
import History from './History'
import QuestionPractice from './QuestionPractice'
import './App.css'

type Theme = 'system' | 'light' | 'dark'
function Workspace() {
  const navigate = useNavigate()
  const location = useLocation()
  const [theme, setTheme] = useState<Theme>(() => { try { const value = localStorage.getItem('ia-theme'); return value === 'dark' || value === 'light' ? value : 'system' } catch { return 'system' } })
  const [menuOpen, setMenuOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [toast, setToast] = useState('')
  useEffect(() => { if (theme === 'system') { document.documentElement.removeAttribute('data-theme'); localStorage.removeItem('ia-theme') } else { document.documentElement.dataset.theme = theme; localStorage.setItem('ia-theme', theme) } }, [theme])
  useEffect(() => { if (!toast) return; const timer = window.setTimeout(() => setToast(''), 3200); return () => window.clearTimeout(timer) }, [toast])
  const page = location.pathname.startsWith('/materials') ? '资料管理' : location.pathname.startsWith('/history') ? '历史记录' : location.pathname.startsWith('/question-practice') ? '试题练习' : '模拟面试'
  const nav = [ { to: '/question-practice', label: '试题练习', Icon: ListChecks }, { to: '/practice', label: '模拟面试', Icon: MessagesSquare }, { to: '/materials', label: '资料管理', Icon: FolderOpen }, { to: '/history', label: '历史记录', Icon: HistoryIcon } ]
  return <div className="app-shell">
    {menuOpen && <button className="nav-scrim" aria-label="关闭导航" onClick={() => setMenuOpen(false)} />}
    <aside className={`sidebar ${menuOpen ? 'is-open' : ''}`}>
      <div className="sidebar-top"><NavLink to="/question-practice" className="brand" onClick={() => setMenuOpen(false)}>面试练习</NavLink><button className="icon-button sidebar-close" aria-label="关闭导航" onClick={() => setMenuOpen(false)}><X size={18} /></button></div>
      <nav aria-label="主导航">{nav.map(({ to, label, Icon }) => <NavLink key={to} end={to !== '/history'} to={to} className={({ isActive }) => `nav-item ${isActive ? 'is-active' : ''}`} onClick={() => setMenuOpen(false)}><Icon size={18} aria-hidden="true" /><span>{label}</span></NavLink>)}</nav>
      <div className="sidebar-bottom"><button className="nav-item nav-button" onClick={() => { setHelpOpen(true); setMenuOpen(false) }}><BookOpenText size={18} aria-hidden="true" />使用说明</button><div className="theme-control"><span>主题</span><div className="theme-options" role="group" aria-label="主题模式">{([{ value: 'system', Icon: Monitor, label: '跟随系统' }, { value: 'light', Icon: Sun, label: '浅色' }, { value: 'dark', Icon: Moon, label: '深色' }] as const).map(({ value, Icon, label }) => <button key={value} title={label} aria-label={label} aria-pressed={theme === value} className={theme === value ? 'is-active' : ''} onClick={() => setTheme(value)}><Icon size={16} /></button>)}</div></div></div>
    </aside>
    <div className="main-shell"><header className="topbar"><button className="icon-button mobile-menu" aria-label="打开导航" onClick={() => setMenuOpen(true)}><Menu size={20} /></button><span className="top-context">{page}</span><span className="top-spacer" /></header><Routes>
      <Route path="/" element={<Navigate to="/question-practice" replace />} />
      <Route path="/practice" element={null} />
      <Route path="/question-practice" element={null} />
      <Route path="/materials" element={null} />
      <Route path="/history" element={null} />
      <Route path="/history/:id" element={null} />
      <Route path="*" element={<Navigate to="/question-practice" replace />} />
    </Routes><div hidden={page !== '模拟面试'}><MockInterview /></div><div hidden={page !== '试题练习'}><QuestionPractice /></div><div hidden={page !== '资料管理'}><Materials notify={setToast} /></div><div hidden={page !== '历史记录'}><History sessions={initialSessions} onPractice={() => navigate('/practice')} /></div></div>
    <Modal open={helpOpen} onOpenChange={setHelpOpen} title="使用说明"><div className="help-content"><p>试题练习可随机抽一道已发布题并立即查看反馈；模拟面试覆盖开场、经历或假设情境、技术、行为与候选人反问，结束后展示报告。两种模式均无需上传资料。</p><p>两种练习的问答与报告来自本机服务。模拟面试入口可回看服务端最近会话；暂停保留当前页面的回答。资料管理与独立历史记录页仍为演示数据。</p></div></Modal>
    {toast && <div className="toast" role="status"><span>{toast}</span><button className="icon-button" aria-label="关闭提示" onClick={() => setToast('')}><X size={16} /></button></div>}
  </div>
}
export default function App() { return <BrowserRouter><Workspace /></BrowserRouter> }
