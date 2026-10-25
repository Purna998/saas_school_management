'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { apiClient } from '@/lib/api/client';
import { useAuthStore } from '@/lib/store/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Brand } from '@/components/layout/Brand';
import { ArrowRight, BookOpen, Check, Eye, EyeOff, GraduationCap, Loader2, LockKeyhole, Mail, ShieldCheck, Users } from 'lucide-react';
import { toast } from 'sonner';

const loginSchema = z.object({
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(6, 'Password must be at least 6 characters'),
});
type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const { setAuth } = useAuthStore();
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [loginError, setLoginError] = useState('');
  const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });

  const onSubmit = async (data: LoginForm) => {
    setIsLoading(true);
    setLoginError('');
    try {
      const response = await apiClient.auth.login(data.email, data.password);
      if (response.success) {
        const { user, tokens } = response.data;
        setAuth({
          id: user.id, email: user.email, full_name: user.full_name_en,
          role: user.roles.includes('super_admin') ? 'super_admin' : user.roles[0] ?? '',
          tenant_id: user.school_id, permissions: user.permissions,
        }, tokens.access_token, tokens.refresh_token);
        toast.success('Welcome back!');
        router.push(user.roles.includes('super_admin') ? '/dashboard/platform' : '/dashboard');
      } else {
        setLoginError(response.error?.message || 'Unable to sign in. Check your email and password.');
      }
    } catch (error: unknown) {
      setLoginError('Unable to connect. Please try again in a moment.');
      console.error('Login error:', error);
    } finally { setIsLoading(false); }
  };

  return (
    <main className="login-shell">
      <div className="login-window">
        <section className="login-story" aria-label="Welcome to Nepal SMS">
          <Brand />
          <div className="relative z-10 my-10">
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/10 bg-white px-3 py-1.5 text-[11px] font-medium text-primary"><span className="size-1.5 rounded-full bg-primary" />A better school day starts here</span>
            <h2 className="mt-6 text-[38px] font-semibold leading-[1.2] tracking-[-1.4px]">One school.<br />Endless possibilities.</h2>
            <p className="mt-4 max-w-80 text-sm leading-7 text-muted-foreground">Bring your school community together. Less administration, more room to learn and grow.</p>
            <div className="login-preview" aria-hidden="true">
              <div className="mb-4 flex items-center justify-between"><span className="text-xs font-semibold">Your school, at a glance</span><span className="flex gap-1"><span className="size-1.5 rounded-full bg-primary/30" /><span className="size-1.5 rounded-full bg-primary/20" /><span className="size-1.5 rounded-full bg-primary/10" /></span></div>
              <div className="grid grid-cols-3 gap-2">
                {[{ icon: Users, label: 'Students', color: 'bg-[#f0e6fc] text-[#a15ed3]' }, { icon: GraduationCap, label: 'Teachers', color: 'bg-[#e4f5fe] text-[#51b3df]' }, { icon: BookOpen, label: 'Learning', color: 'bg-[#fff0e8] text-[#ed9c6d]' }].map((item) => <div key={item.label} className={`rounded-lg p-3 ${item.color}`}><item.icon className="mb-2 size-5" /><span className="text-[10px] font-medium">{item.label}</span></div>)}
              </div>
              <div className="mt-4 flex items-end gap-3 rounded-lg bg-[#fcfafe] px-4 pb-3 pt-5">
                {[35, 55, 42, 72, 48, 90, 62, 78, 52, 68, 84, 59].map((height, index) => <div key={index} className="flex flex-1 items-end justify-center gap-1"><div className="login-preview-bar" style={{ height: height * .7 }} /><div className="login-preview-bar !bg-[#ffac76]" style={{ height: height * .48 }} /></div>)}
              </div>
            </div>
          </div>
          <p className="relative flex items-center gap-2 text-xs text-muted-foreground"><Check className="size-4 text-primary" />Connected people. Inspired learning.</p>
        </section>

        <section className="flex flex-col justify-between px-7 py-8 sm:px-12 sm:py-10 lg:px-16">
          <div className="mb-10 flex items-center justify-between"><Brand className="md:hidden" /><span className="ml-auto flex items-center gap-1.5 rounded-full bg-[#f8f5fb] px-3 py-1.5 text-[10px] text-muted-foreground"><ShieldCheck className="size-3.5 text-primary" />Your school. Securely connected.</span></div>
          <div className="py-2">
            <span className="mb-5 flex size-12 items-center justify-center rounded-2xl bg-accent text-primary"><GraduationCap className="size-6" strokeWidth={1.7} /></span>
            <h1 className="text-[30px] font-semibold tracking-[-.8px]">Welcome back</h1>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">Sign in to your school workspace.</p>
            <form onSubmit={handleSubmit(onSubmit)} className="mt-8 space-y-5" noValidate>
              <div className="space-y-2">
                <label htmlFor="email" className="text-xs font-medium">Email address</label>
                <div className="relative"><Mail className="pointer-events-none absolute left-3.5 top-3.5 size-4 text-muted-foreground/70" /><Input id="email" type="email" autoComplete="username" placeholder="you@school.edu.np" className="h-11 pl-10" {...register('email')} disabled={isLoading} aria-invalid={!!errors.email} aria-describedby={errors.email ? 'email-error' : undefined} /></div>
                {errors.email && <p id="email-error" className="text-xs text-destructive">{errors.email.message}</p>}
              </div>
              <div className="space-y-2">
                <label htmlFor="password" className="text-xs font-medium">Password</label>
                <div className="relative"><LockKeyhole className="pointer-events-none absolute left-3.5 top-3.5 size-4 text-muted-foreground/70" /><Input id="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" placeholder="Enter your password" className="h-11 pl-10 pr-11" {...register('password')} disabled={isLoading} aria-invalid={!!errors.password} aria-describedby={errors.password ? 'password-error' : undefined} /><button type="button" className="absolute right-1 top-1 flex size-9 items-center justify-center rounded-lg text-muted-foreground hover:text-primary" aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword} onClick={() => setShowPassword((value) => !value)}>{showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button></div>
                {errors.password && <p id="password-error" className="text-xs text-destructive">{errors.password.message}</p>}
              </div>
              {loginError && <p role="alert" className="rounded-lg bg-destructive/5 p-3 text-xs leading-5 text-destructive">{loginError}</p>}
              <Button type="submit" className="h-12 w-full" disabled={isLoading}>{isLoading ? <><Loader2 className="animate-spin" />Signing in…</> : <>Sign in to your workspace<ArrowRight className="ml-1" /></>}</Button>
            </form>
            <p className="mt-6 text-center text-xs leading-6 text-muted-foreground">Need access or help signing in?<br /><span className="font-medium text-foreground/80">Contact your school administrator.</span></p>
          </div>
          <div className="mt-10 border-t pt-5 text-center text-[11px] text-muted-foreground"><p>विद्यालय व्यवस्थापन प्रणाली</p><p className="mt-2">© 2026 Nepal SMS. All rights reserved.</p></div>
        </section>
      </div>
    </main>
  );
}
