import assert from 'node:assert/strict';
import { test } from 'node:test';
import { apiClient } from '../lib/api/client';

test('GET deduplication shares a session request and isolates another login in the same school', async () => {
  const originalFetch = globalThis.fetch;
  const requests: Array<{ authorization: string; finish: (value: Response) => void }> = [];
  globalThis.fetch = (_input, init) => new Promise<Response>((finish) => {
    requests.push({ authorization: (init?.headers as Record<string, string>).Authorization, finish });
  });
  localStorage.setItem('tenant_id', 'test-school');
  localStorage.setItem('access_token', 'first-session');
  try {
    const first = apiClient.students.roster(2, 'A');
    const duplicate = apiClient.students.roster(2, 'A');
    assert.equal(first, duplicate);
    assert.equal(requests.length, 1);
    localStorage.setItem('access_token', 'second-session');
    const second = apiClient.students.roster(2, 'A');
    assert.notEqual(first, second);
    assert.equal(requests.length, 2);
    assert.deepEqual(requests.map((request) => request.authorization), ['Bearer first-session', 'Bearer second-session']);
    for (const request of requests) request.finish(new Response(JSON.stringify({ students: [], total: 0 }), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    }));
    assert.equal((await first).success, true);
    assert.equal((await second).success, true);
  } finally {
    globalThis.fetch = originalFetch;
    localStorage.clear();
  }
});
