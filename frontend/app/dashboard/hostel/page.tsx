'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { HostelEmpty, HostelStat, useHostelAccess, useHostelToday } from '@/components/hostel/HostelCommon';
import { HostelResidents } from '@/components/hostel/HostelResidents';
import type { StayAction } from '@/components/hostel/HostelResidents';
import { apiClient } from '@/lib/api/client';
import { hostelData } from '@/lib/api/hostel';
import type { Hostel, HostelBed, HostelRoom, Resident } from '@/lib/api/hostel';

const loading = () => <HostelEmpty>Loading hostel workspace…</HostelEmpty>;
const HostelSetup = dynamic(() => import('@/components/hostel/HostelSetup').then((module) => module.HostelSetup), { loading });
const HostelEditor = dynamic(() => import('@/components/hostel/HostelSetup').then((module) => module.HostelEditor), { loading });
const RoomEditor = dynamic(() => import('@/components/hostel/HostelSetup').then((module) => module.RoomEditor), { loading });
const HostelInventory = dynamic(() => import('@/components/hostel/HostelInventory').then((module) => module.HostelInventory), { loading });
const HostelAdmission = dynamic(() => import('@/components/hostel/HostelAdmission').then((module) => module.HostelAdmission), { loading });
const HostelStayDialog = dynamic(() => import('@/components/hostel/HostelResidents').then((module) => module.HostelStayDialog), { loading });
const HostelOperationDialog = dynamic(() => import('@/components/hostel/HostelOperations').then((module) => module.HostelOperationDialog), { loading });
const HostelBillDialog = dynamic(() => import('@/components/hostel/HostelOperations').then((module) => module.HostelBillDialog), { loading });
const HostelMovements = dynamic(() => import('@/components/hostel/HostelMovements').then((module) => module.HostelMovements), { loading });
const MovementCloseDialog = dynamic(() => import('@/components/hostel/HostelMovements').then((module) => module.MovementCloseDialog), { loading });
const HostelRegister = dynamic(() => import('@/components/hostel/HostelRegister').then((module) => module.HostelRegister), { loading });
const HostelReports = dynamic(() => import('@/components/hostel/HostelReports').then((module) => module.HostelReports), { loading });

type Modal = { type: 'hostel'; hostel?: Hostel } | { type: 'room'; hostel: Hostel; room?: HostelRoom } | { type: 'beds'; room: HostelRoom } | { type: 'admit'; room?: HostelRoom; bed?: HostelBed; transfer?: Resident } | { type: 'resident'; id: string } | { type: 'operation'; action: 'checkout' | 'leave' | 'returnLeave' | 'visit'; stay: Resident } | { type: 'bill'; stay: Resident } | { type: 'closeMovement'; kind: 'leave' | 'visit'; id: string; label: string } | null;

export default function HostelPage() {
  const access = useHostelAccess(); const queryClient = useQueryClient(); const today = useHostelToday(); const [tab, setTab] = useState('residents'); const [registerDirty, setRegisterDirty] = useState(false); const [modal, setModal] = useState<Modal>(null);
  const stats = useQuery({ queryKey: ['hostel', 'stats', null], queryFn: async () => hostelData(await apiClient.hostel.stats()), enabled: access.canRead });
  const close = () => setModal(null); const onResident = (id: string) => setModal({ type: 'resident', id }); const onAllocate = (room?: HostelRoom, bed?: HostelBed) => setModal({ type: 'admit', room, bed });
  const onAction = (action: StayAction, stay: Resident) => { if (action === 'transfer') setModal({ type: 'admit', transfer: stay }); else if (action === 'bill') setModal({ type: 'bill', stay }); else setModal({ type: 'operation', action, stay }); };
  if (!access.canRead) return <HostelEmpty>Residential records require hostel access from an authorized school staff account.</HostelEmpty>;
  return <div className="space-y-6"><header className="flex flex-wrap items-center justify-between gap-4"><div><h1>Hostel / छात्रावास</h1><p className="text-muted-foreground">Boarding records, wardens, rooms and daily residential care.{today.data && ` ${today.data.bs} BS · ${today.data.ad} AD`}</p></div><div className="flex gap-2"><Button variant="outline" disabled={stats.isFetching || registerDirty} onClick={() => queryClient.invalidateQueries({ queryKey: ['hostel'] })}><RefreshCw className={stats.isFetching ? 'animate-spin' : ''} />Refresh</Button>{access.canAllocate && <Button disabled={registerDirty} onClick={() => onAllocate()}><Plus />Admit boarder</Button>}</div></header>
    <section aria-label="School hostel totals">{stats.error ? <HostelEmpty error={stats.error.message} /> : <div className="pastel-summary grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><HostelStat label="Current boarders" value={stats.data?.total_occupied ?? '…'} /><HostelStat label="Available beds" value={stats.data?.available_beds ?? '…'} /><HostelStat label="On approved leave" value={stats.data?.on_leave ?? '…'} /><HostelStat label="Past expected return date" value={stats.data?.overdue_returns ?? '…'} /></div>}</section>
    <nav aria-label="Hostel sections" className="section-tabs">{[['residents', 'Residents'], ['setup', 'Hostels & rooms'], ['register', 'Attendance & meals'], ['leaves', 'Leave & returns'], ['visits', 'Visitors'], ['reports', 'Reports & activity']].map(([id, title]) => <Button key={id} disabled={registerDirty} variant={tab === id ? 'default' : 'ghost'} aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}>{title}</Button>)}</nav>
    <Card><CardContent className="pt-5">{tab === 'residents' && <HostelResidents canAllocate={access.canAllocate} onAdmit={() => onAllocate()} onResident={onResident} />}{tab === 'setup' && <HostelSetup {...access} onHostel={(hostel) => setModal({ type: 'hostel', hostel })} onRoom={(hostel, room) => setModal({ type: 'room', hostel, room })} onBeds={(room) => setModal({ type: 'beds', room })} onAllocate={onAllocate} />}{tab === 'register' && <HostelRegister canAllocate={access.canAllocate} onDirtyChange={setRegisterDirty} />}{(tab === 'leaves' || tab === 'visits') && <HostelMovements key={tab} kind={tab} canAllocate={access.canAllocate} onResident={onResident} onResidents={() => setTab('residents')} onCloseRecord={(kind, id, label) => setModal({ type: 'closeMovement', kind, id, label })} />}{tab === 'reports' && <HostelReports />}</CardContent></Card>
    {modal?.type === 'hostel' && access.canEdit && <HostelEditor hostel={modal.hostel} onClose={close} />}
    {modal?.type === 'room' && access.canEdit && <RoomEditor hostel={modal.hostel} room={modal.room} onClose={close} />}
    {modal?.type === 'beds' && <HostelInventory roomId={modal.room.id} canEdit={access.canEdit} canAllocate={access.canAllocate} onClose={close} onAllocate={onAllocate} onResident={onResident} />}
    {modal?.type === 'admit' && access.canAllocate && <HostelAdmission initialRoom={modal.room} bedId={modal.bed?.id} bedLabel={modal.bed?.label} transfer={modal.transfer} onClose={close} onResident={onResident} />}
    {modal?.type === 'resident' && <HostelStayDialog allocationId={modal.id} canAllocate={access.canAllocate} canBill={access.canBill} onClose={close} onAction={onAction} />}
    {modal?.type === 'operation' && access.canAllocate && <HostelOperationDialog action={modal.action} stay={modal.stay} onClose={close} onResident={onResident} />}
    {modal?.type === 'bill' && access.canBill && <HostelBillDialog stay={modal.stay} onClose={close} />}
    {modal?.type === 'closeMovement' && access.canAllocate && <MovementCloseDialog kind={modal.kind} recordId={modal.id} label={modal.label} onClose={close} />}
  </div>;
}
