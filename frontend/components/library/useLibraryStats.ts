'use client';

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { libraryData } from '@/lib/api/library';
import { useAuthStore } from '@/lib/store/auth';

export function useLibraryAccess() {
  const user = useAuthStore((state) => state.user);
  const has = (permission: string) => Boolean(user?.permissions?.includes(permission) || user?.permissions?.includes('*:*'));
  const canCreate = has('library:create');
  const canEdit = has('library:update');
  const canIssue = has('library:issue');
  const canReturn = has('library:return');
  const canRead = has('library:read');
  const privateAccess = !['parent', 'student'].includes(user?.role ?? '') || canCreate || canEdit || canIssue || canReturn;
  return { canRead, canCreate, canEdit, canIssue, canReturn, privateAccess };
}

export function useLibraryStats() {
  const access = useLibraryAccess();
  return useQuery({ queryKey: ['library', 'stats'], queryFn: async () => libraryData(await apiClient.library.stats()), enabled: access.canRead && access.privateAccess });
}
