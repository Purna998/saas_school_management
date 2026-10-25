'use client';

import dynamic from 'next/dynamic';

const ChartLoading = () => <div className="h-[300px] animate-pulse rounded bg-muted" />;

export const StudentsByGradeChart = dynamic(
  () => import('./DashboardCharts').then((module) => module.StudentsByGradeChart),
  { loading: ChartLoading },
);

export const AttendanceTrendChart = dynamic(
  () => import('./DashboardCharts').then((module) => module.AttendanceTrendChart),
  { loading: ChartLoading },
);

export const FeeCollectionChart = dynamic(
  () => import('./DashboardCharts').then((module) => module.FeeCollectionChart),
  { loading: ChartLoading },
);
