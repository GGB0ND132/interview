// Real HTTP/provider; synthetic JD and resume. Start at /practice setup.
async (page) => {
  await page.getByLabel('岗位 JD（可选）').fill('熟悉工具调用和 Agent 运行循环，能够处理失败重试；熟悉 Kubernetes 集群运维。');
  await page.getByRole('button', { name: '提取岗位要求', exact: true }).click();
  await page.getByRole('button', { name: '确认要求并接受覆盖缺口', exact: true }).click();
  await page.getByText('已确认，本场将使用所选 JD 要求。', { exact: true }).waitFor();
  await page.getByLabel('上传简历（可选）').setInputFiles('output/playwright/17-resume.docx');
  await page.getByRole('button', { name: '确认所选项目', exact: true }).click();
  await page.getByText('已确认，本场使用所选项目陈述。', { exact: true }).waitFor();
  await page.getByRole('button', { name: '开始模拟面试', exact: true }).click();
  await page.getByRole('textbox', { name: '你的回答' }).waitFor();
  const draft = '这是合成验收回答。我是计算机专业学生，做过订单 Agent 课程练习，负责工具参数校验、权限检查和失败停止机制，希望学习可靠的工具执行与恢复。';
  await page.getByRole('textbox', { name: '你的回答' }).fill(draft);
  await page.reload();
  if (await page.getByRole('textbox', { name: '你的回答' }).inputValue() !== draft) throw new Error('Mock draft lost');
  const id = await page.evaluate(() => localStorage.getItem('ia-mi-session'));
  const session = (await (await page.request.get(new URL(`/api/v1/sessions/${id}`, page.url()).href)).json()).data;
  return { session_id: id, draft_restored: true, selected_topics: session.plan.selected_topics,
    selection_algorithm: session.plan.selection_algorithm, topic_candidates: session.plan.topic_candidates,
    topic_draws: session.plan.topic_draws, jd: session.jd, resume_context: session.resume_context };
}
