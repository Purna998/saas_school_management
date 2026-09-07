'use client';

import { useEffect, useState } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Users,
  UserCog,
  GraduationCap,
  DollarSign,
  TrendingUp,
  TrendingDown,
  BookOpen,
  ClipboardCheck,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell } from 'recharts';

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

export default function DashboardPage() {
  const [stats, setStats] = useState({
    totalStudents: 1250,
    totalStaff: 85,
    totalClasses: 45,
    pendingFees: 125000,
    studentGrowth: 12.5,
    attendanceRate: 94.2,
  });

  const studentsByGrade = [
    { grade: 'Nursery', count: 45 },
    { grade: 'LKG', count: 52 },
    { grade: 'UKG', count: 48 },
    { grade: 'Grade 1', count: 95 },
    { grade: 'Grade 2', count: 88 },
    { grade: 'Grade 3', count: 92 },
    { grade: 'Grade 4', count: 85 },
    { grade: 'Grade 5', count: 90 },
    { grade: 'Grade 6', count: 82 },
    { grade: 'Grade 7', count: 78 },
    { grade: 'Grade 8', count: 75 },
    { grade: 'Grade 9', count: 72 },
    { grade: 'Grade 10', count: 68 },
    { grade: 'Grade 11', count: 45 },
    { grade: 'Grade 12', count: 35 },
  ];

  const attendanceTrend = [
    { month: 'Jan', attendance: 92.5 },
    { month: 'Feb', attendance: 93.2 },
    { month: 'Mar', attendance: 91.8 },
    { month: 'Apr', attendance: 94.1 },
    { month: 'May', attendance: 93.8 },
    { month: 'Jun', attendance: 94.2 },
  ];

  const feeCollection = [
    { name: 'Collected', value: 875000 },
    { name: 'Pending', value: 125000 },
  ];

  const statCards = [
    {
      title: 'Total Students',
      value: stats.totalStudents,
      icon: Users,
      trend: stats.studentGrowth,
      trendUp: true,
      color: 'bg-blue-500',
    },
    {
      title: 'Total Staff',
      value: stats.totalStaff,
      icon: UserCog,
      trend: 5.2,
      trendUp: true,
      color: 'bg-green-500',
    },
    {
      title: 'Total Classes',
      value: stats.totalClasses,
      icon: GraduationCap,
      trend: 0,
      trendUp: true,
      color: 'bg-purple-500',
    },
    {
      title: 'Pending Fees',
      value: `NPR ${stats.pendingFees.toLocaleString()}`,
      icon: DollarSign,
      trend: -8.3,
      trendUp: false,
      color: 'bg-orange-500',
    },
  ];

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Welcome back! Here's what's happening with your school today.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {statCards.map((stat) => (
            <Card key={stat.title}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">{stat.title}</CardTitle>
                <div className={`rounded-full p-2 ${stat.color}`}>
                  <stat.icon className="h-4 w-4 text-white" />
                </div>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stat.value}</div>
                {stat.trend !== 0 && (
                  <div className="flex items-center text-xs text-muted-foreground">
                    {stat.trendUp ? (
                      <TrendingUp className="mr-1 h-4 w-4 text-green-500" />
                    ) : (
                      <TrendingDown className="mr-1 h-4 w-4 text-red-500" />
                    )}
                    <span className={stat.trendUp ? 'text-green-500' : 'text-red-500'}>
                      {Math.abs(stat.trend)}%
                    </span>
                    <span className="ml-1">from last month</span>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Students by Grade</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={studentsByGrade}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="grade" angle={-45} textAnchor="end" height={80} />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="count" fill="#3b82f6" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Attendance Trend (Last 6 Months)</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={attendanceTrend}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" />
                  <YAxis domain={[85, 100]} />
                  <Tooltip />
                  <Line type="monotone" dataKey="attendance" stroke="#10b981" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Fee Collection Status</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={feeCollection}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name}: ${((percent || 0) * 100).toFixed(0)}%`}
                    outerRadius={100}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {feeCollection.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Quick Stats</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ClipboardCheck className="h-5 w-5 text-green-500" />
                  <span className="text-sm">Today's Attendance</span>
                </div>
                <span className="text-lg font-bold">{stats.attendanceRate}%</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <BookOpen className="h-5 w-5 text-blue-500" />
                  <span className="text-sm">Library Books Issued</span>
                </div>
                <span className="text-lg font-bold">342</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Users className="h-5 w-5 text-purple-500" />
                  <span className="text-sm">New Admissions (This Month)</span>
                </div>
                <span className="text-lg font-bold">28</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <GraduationCap className="h-5 w-5 text-orange-500" />
                  <span className="text-sm">Upcoming Exams</span>
                </div>
                <span className="text-lg font-bold">5</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
}
