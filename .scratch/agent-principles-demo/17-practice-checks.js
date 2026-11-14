// From the restored single-question feedback page; captures blank vs skipped.
async (page) => {
  const read = async () => {
    const id = await page.evaluate(() => localStorage.getItem('ia-qp-session'));
    return (await (await page.request.get(new URL(`/api/v1/sessions/${id}`, page.url()).href)).json()).data;
  };
  const original = await read();
  await page.getByRole('heading', { name: '本题反馈', exact: true }).waitFor();
  await page.screenshot({ path: 'output/playwright/17-single-feedback.png', fullPage: true });
  const results = [{ case: 'live_answer_restored', session_id: original.session_id,
    score: original.submissions[0].score, feedback_model: original.submissions[0].feedback.requested_model }];
  for (const [button, expectedScore] of [['空白提交', 0], ['跳过本题', null]]) {
    await page.getByRole('button', { name: '返回练习入口', exact: true }).click();
    await page.getByRole('button', { name: '随机抽一题', exact: true }).click();
    await page.getByRole('button', { name: button, exact: true }).click();
    await page.getByRole('heading', { name: expectedScore === 0 ? '本题反馈' : '已跳过', exact: true }).waitFor();
    const saved = await read();
    const report = (await (await page.request.get(new URL(`/api/v1/sessions/${saved.session_id}/report`, page.url()).href)).json()).data;
    if (saved.submissions[0].score !== expectedScore || report.average_score !== expectedScore || saved.submissions[0].job_id) throw new Error('Disposition score/model-call mismatch');
    if (report.answered_count !== (expectedScore === 0 ? 1 : 0)) throw new Error('Wrong denominator');
    results.push({ case: button, session_id: saved.session_id, score: expectedScore,
      answered_count: report.answered_count, blank_count: report.blank_count, skipped_count: report.skipped_count });
    await page.reload();
    await page.getByRole('heading', { name: expectedScore === 0 ? '本题反馈' : '已跳过', exact: true }).waitFor();
  }
  return results;
}
