// After restarting the SAME controlled database with --outcome success.
async (page) => {
  const results = [];
  for (const [route, key] of [['/question-practice', 'ia-qp-session'], ['/practice', 'ia-mi-session']]) {
    await page.goto(new URL(route, page.url()).href);
    await page.getByRole('button', { name: '重试评价', exact: true }).waitFor();
    const id = await page.evaluate(key => localStorage.getItem(key), key);
    const read = async () => (await (await page.request.get(new URL(`/api/v1/sessions/${id}`, page.url()).href)).json()).data;
    const before = await read();
    await page.getByRole('button', { name: '重试评价', exact: true }).click();
    if (route === '/practice') await page.getByRole('button', { name: '继续下一组', exact: true }).waitFor();
    else await page.getByRole('heading', { name: '本题反馈', exact: true }).waitFor();
    await page.reload();
    if (route === '/practice') await page.getByRole('button', { name: '继续下一组', exact: true }).waitFor();
    else await page.getByRole('heading', { name: '本题反馈', exact: true }).waitFor();
    const saved = await read();
    const job = (await (await page.request.get(new URL(`/api/v1/jobs/${before.submissions[0].job_id}`, page.url()).href)).json()).data;
    if (saved.submissions.length !== 1 || saved.submissions[0].id !== before.submissions[0].id || job.attempts !== 2 || job.status !== 'succeeded') throw new Error('Retry duplicated or failed');
    if (route === '/practice' && 'feedback' in saved.submissions[0]) throw new Error('Interview score exposed early');
    results.push({ session_id: id, mode: saved.mode, restored_after_restart: true, submissions: 1, attempts: job.attempts, job_status: job.status, phase: saved.phase });
    await page.screenshot({ path: `output/playwright/17-retry-${key}.png` });
  }
  return results;
}
