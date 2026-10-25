'use client';

import { useId } from 'react';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell,
  Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';

const tooltipStyle = { borderRadius: 12, border: '1px solid #eee7f4', boxShadow: '0 6px 24px #5522770b', fontSize: 12, color: '#251d32' };
const tick = { fill: '#938b9b', fontSize: 10 };

export function StudentsByGradeChart({ data }: { data: { grade: string; count: number }[] }) {
  return (
    <div role="img" aria-label={`Sample student enrollment by grade: ${data.map((item) => `${item.grade}, ${item.count}`).join('; ')}`}>
      <ResponsiveContainer width="100%" height={275}>
        <BarChart data={data} margin={{ top: 12, right: 12, left: -22, bottom: 5 }} barSize={10}>
          <CartesianGrid strokeDasharray="2 5" vertical={false} stroke="#e7e1ed" />
          <XAxis dataKey="grade" tick={tick} axisLine={false} tickLine={false} tickFormatter={(value: string) => value.replace('Grade ', 'G')} minTickGap={8} dy={8} />
          <YAxis tick={tick} axisLine={false} tickLine={false} />
          <Tooltip cursor={{ fill: '#f7f0fc', radius: 6 }} contentStyle={tooltipStyle} />
          <Bar dataKey="count" name="Students" fill="#a047d1" radius={[6, 6, 6, 6]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function AttendanceTrendChart({ data }: { data: { month: string; attendance: number }[] }) {
  const gradientId = useId();
  return (
    <div role="img" aria-label={`Sample monthly attendance: ${data.map((item) => `${item.month}, ${item.attendance}%`).join('; ')}`}>
      <ResponsiveContainer width="100%" height={250}>
        <AreaChart data={data} margin={{ top: 15, right: 15, left: -14, bottom: 5 }}>
          <defs><linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#ad59d9" stopOpacity={.18} /><stop offset="100%" stopColor="#ad59d9" stopOpacity={0} /></linearGradient></defs>
          <CartesianGrid strokeDasharray="2 5" vertical={false} stroke="#e7e1ed" />
          <XAxis dataKey="month" tick={tick} axisLine={false} tickLine={false} dy={8} />
          <YAxis domain={[85, 100]} tick={tick} axisLine={false} tickLine={false} tickFormatter={(value: number) => `${value}%`} />
          <Tooltip contentStyle={tooltipStyle} />
          <Area type="monotone" dataKey="attendance" name="Attendance (%)" stroke="#a047d1" strokeWidth={2.5} fill={`url(#${gradientId})`} dot={{ r: 4, fill: '#fff', strokeWidth: 2 }} activeDot={{ r: 6 }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function FeeCollectionChart({ data }: { data: { name: string; value: number }[] }) {
  const total = data.reduce((sum, item) => sum + item.value, 0);
  const collected = total ? Math.round(((data.find((item) => item.name === 'Collected')?.value ?? 0) / total) * 1000) / 10 : 0;
  return (
    <div className="relative" role="img" aria-label={`Fee collection: ${collected}% collected. ${data.map((item) => `${item.name}, NPR ${item.value.toLocaleString()}`).join('; ')}`}>
      <ResponsiveContainer width="100%" height={215}>
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius={72} outerRadius={95} paddingAngle={5} cornerRadius={12} startAngle={90} endAngle={-270} stroke="none" dataKey="value">
            {data.map((entry, index) => <Cell key={entry.name} fill={index === 0 ? '#921ed1' : '#ffa365'} />)}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center"><span className="text-xs text-muted-foreground">Collected</span><span className="mt-1 text-3xl font-semibold tracking-tight">{collected}%</span></div>
    </div>
  );
}
