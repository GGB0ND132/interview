// Playwright CLI run-code --filename. One real-model answer per invocation.
// Start through the JD confirmation UI first. All answers are synthetic fixtures.
async (page) => {
  const id = await page.evaluate(() => localStorage.getItem('ia-mi-session'));
  if (!id) throw new Error('Start a session through the browser first');
  const read = async () => (await (await page.request.get(new URL(`/api/v1/sessions/${id}`, page.url()).href)).json()).data;
  let session = await read();
  if (session.status === 'completed' || session.status === 'ended_early') {
    await page.getByRole('heading', { name: /面试报告/ }).waitFor();
    return { session_id: id, status: session.status, report_visible: true };
  }
  if (session.phase === 'stage_transition') {
    await page.getByRole('button', { name: '继续下一组' }).click();
    await page.getByRole('textbox', { name: '你的回答' }).waitFor();
    session = await read();
  }
  const answers = {
    introduction: '我是一名计算机专业学生，最近学习 Agent 的工具调用和执行循环，做过课程中的订单查询练习。我负责接口参数校验和失败记录，希望学习如何把模型能力接入可靠的业务流程。',
    scenario: '在这个假设情境中，模型理解请求并选择允许的查询工具，程序校验参数和访问权限后实际执行查询，把结果或结构化错误交回模型。权限失败停止，超时有限重试，设置最多三轮和总超时。分别测试成功、无权限、订单不存在和超时，核对日志，避免越权与无限循环。',
    behavioral: '课程小组的接口字段名不一致，导致联调失败。我整理请求响应样例，和同学逐项确认，统一字段后补充失败样例。最终四个接口能对接；复盘发现沟通太晚，下次会在编码前确定契约，安排早期联调。',
    candidate_questions: '团队如何验证 Agent 工具调用的失败恢复和权限边界？新人从哪些场景入手，如何获得代码审查和反馈？',
  };
  if (session.phase === 'evaluation_failed') {
    await page.getByRole('button', { name: '重试评价' }).click();
    await page.getByRole('button', { name: '重试评价' }).waitFor({ state: 'hidden' });
  } else if (session.phase === 'awaiting_answer') {
    const turn = session.current_turn;
    const answer = answers[turn.stage] || `这道题我不会，我不清楚${turn.topic}的具体机制和边界，需要继续学习。`;
    await page.getByRole('textbox', { name: '你的回答' }).fill(answer);
    await page.getByRole('button', { name: '提交回答', exact: true }).click();
    await page.getByRole('button', { name: '提交回答', exact: true }).waitFor({ state: 'hidden' });
  }
  await page.getByRole('button', { name: /继续下一组|重试评价/ }).or(page.getByRole('heading', { name: /面试报告/ })).or(page.getByRole('textbox', { name: '你的回答' })).first().waitFor({ timeout: 60000 });
  const updated = await read();
  return { session_id: id, stage: session.current_turn.stage, phase: updated.phase, status: updated.status, revision: updated.revision, turns: updated.turns.length };
}
