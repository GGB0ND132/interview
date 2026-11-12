// Final-code browser smoke checks, real API, no mocked responses or model calls.
async (page) => {
  const cases = [];
  for (const text of [null, '熟悉工具调用与 Function Calling']) {
    await page.getByRole('button', { name: '返回模拟面试入口' }).click();
    await page.getByRole('textbox', { name: '岗位 JD（可选）' }).waitFor();
    if (text) {
      await page.getByRole('textbox', { name: '岗位 JD（可选）' }).fill(text);
      await page.getByRole('button', { name: '提取岗位要求', exact: true }).click();
      await page.getByRole('button', { name: '确认所选要求', exact: true }).click();
      await page.getByText('已确认，本场将使用所选 JD 要求。', { exact: true }).waitFor();
    }
    await page.getByRole('button', { name: '开始模拟面试', exact: true }).click();
    await page.getByRole('textbox', { name: '你的回答' }).waitFor();
    await page.getByText('本场主题抽选与 JD', { exact: true }).click();
    const id = await page.evaluate(() => localStorage.getItem('ia-mi-session'));
    const session = (await (await page.request.get(new URL(`/api/v1/sessions/${id}`, page.url()).href)).json()).data;
    const weights = session.plan.topic_candidates.map(item => ({ id: item.competency_id, weight: item.weight }));
    if (text ? !session.jd || session.jd.requirements.some(item => item.gap_reason) : Boolean(session.jd)) throw new Error('Unexpected JD snapshot');
    if (weights.some(item => item.weight !== (text && item.id === 'agent_tool_calling' ? 4 : 1))) throw new Error('Unexpected draw weight');
    await page.getByRole('button', { name: '结束面试', exact: true }).click();
    await page.getByRole('button', { name: '结束并生成报告', exact: true }).click();
    await page.getByRole('heading', { name: '部分面试报告', exact: true }).waitFor();
    cases.push({ case: text ? 'confirmed_jd_final_code' : 'no_jd_final_code', session_id: id, text, weights, selected_topics: session.plan.selected_topics });
  }
  return cases;
}
