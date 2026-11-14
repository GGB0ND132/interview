// Run against the explicitly controlled --outcome failure service, never live model.
async (page) => {
  const results = [];
  for (const [route, key, start] of [
    ['/question-practice', 'ia-qp-session', '随机抽一题'],
    ['/practice', 'ia-mi-session', '开始模拟面试'],
  ]) {
    await page.goto(new URL(route, page.url()).href);
    await page.getByRole('button', { name: start, exact: true }).click();
    const text = `合成受控恢复验收 ${key}：模型提出工具调用，程序检查权限与参数后实际执行，再保存真实回执；失败时保留回答。`;
    await page.getByRole('textbox', { name: '你的回答' }).fill(text);
    await page.reload();
    if (await page.getByRole('textbox', { name: '你的回答' }).inputValue() !== text) throw new Error('Draft not restored');
    await page.getByRole('button', { name: '提交回答', exact: true }).click();
    await page.getByRole('button', { name: '重试评价', exact: true }).waitFor();
    await page.reload();
    await page.getByRole('button', { name: '重试评价', exact: true }).waitFor();
    const id = await page.evaluate(key => localStorage.getItem(key), key);
    const session = (await (await page.request.get(new URL(`/api/v1/sessions/${id}`, page.url()).href)).json()).data;
    if (session.submissions.length !== 1 || session.submissions[0].answer_text !== text || session.phase !== 'evaluation_failed') throw new Error('Saved failure differs');
    results.push({ mode: session.mode, session_id: id, job_id: session.submissions[0].job_id, draft_restored: true, failed_answer_restored: true });
  }
  return results;
}
