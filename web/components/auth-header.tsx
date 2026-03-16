'use client'

import { useState, useEffect } from 'react'
import { supabase } from '@/lib/supabase'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { Session } from '@supabase/supabase-js'

export function AuthHeader() {
  const [session, setSession] = useState<Session | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => setSession(session))
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_e, s) => setSession(s))
    return () => subscription.unsubscribe()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setMessage('')
    if (isLogin) {
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) setMessage(error.message)
      else { setShowForm(false); setEmail(''); setPassword('') }
    } else {
      const { error } = await supabase.auth.signUp({ email, password })
      if (error) setMessage(error.message)
      else setMessage('注册成功，请查看邮箱验证链接')
    }
    setLoading(false)
  }

  const handleLogout = async () => {
    await supabase.auth.signOut()
    setSession(null)
  }

  if (session) {
    return (
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground hidden sm:inline">{session.user.email}</span>
        <Button variant="outline" size="sm" onClick={handleLogout}>退出</Button>
      </div>
    )
  }

  if (!showForm) {
    return (
      <Button variant="outline" size="sm" onClick={() => setShowForm(true)}>登录</Button>
    )
  }

  return (
    <div className="flex flex-col gap-2 w-full max-w-xs">
      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <Input
          type="email"
          placeholder="邮箱"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="h-8 text-sm"
        />
        <Input
          type="password"
          placeholder="密码"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          className="h-8 text-sm"
        />
        {message && <p className="text-xs text-muted-foreground">{message}</p>}
        <div className="flex gap-2">
          <Button type="submit" size="sm" className="flex-1" disabled={loading}>
            {loading ? '...' : isLogin ? '登录' : '注册'}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => { setIsLogin(!isLogin); setMessage('') }}
          >
            {isLogin ? '注册' : '登录'}
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={() => setShowForm(false)}>✕</Button>
        </div>
      </form>
    </div>
  )
}
