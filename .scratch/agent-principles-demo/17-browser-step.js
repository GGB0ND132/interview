// One UI action per invocation, so model latency/failures stay visible.
// Every answer is a synthetic acceptance fixture, never a real person's resume.
async (page) => {
  const id = await page.evaluate(() => localStorage.getItem('ia-mi-session'));
  const read = async () => (await (await page.request.get(new URL(`/api/v1/sessions/${id}`, page.url()).href)).json()).data;
  const session = await read();
  if (session.phase === 'evaluating') return { session_id: id, phase: session.phase };
  if (session.status === 'completed' || session.status === 'ended_early') {
    await page.getByRole('heading', { name: /面试报告/, level: 1 }).waitFor();
    await page.reload();
    await page.getByRole('heading', { name: /面试报告/, level: 1 }).waitFor();
    const report = (await (await page.request.get(new URL(`/api/v1/sessions/${id}/report`, page.url()).href)).json()).data;
    await page.screenshot({ path: 'output/playwright/17-mock-report.png', fullPage: true });
    return { session_id: id, phase: session.phase, status: session.status, report_restored: true,
      completeness: report.completeness, jd_gaps: report.jd_gaps, groups: report.groups.length,
      stages: [...new Set(report.turns.map(turn => turn.stage))] };
  }
  if (session.phase === 'evaluation_failed') {
    await page.getByRole('button', { name: '重试评价', exact: true }).click();
    return { session_id: id, retried_error: session.submissions.at(-1).error };
  }
  if (session.phase === 'stage_transition') {
    await page.getByRole('button', { name: '继续下一组', exact: true }).click();
    return { session_id: id, action: 'next', phase: (await read()).phase };
  }
  const turn = session.current_turn;
  const answers = {
    introduction: '这是合成验收回答。我是计算机专业学生，做过订单 Agent 课程练习，负责工具参数校验、权限检查和失败停止机制，希望学习可靠的工具执行与恢复。',
    experience: turn.kind === 'followup'
      ? '我具体在工具执行前校验订单编号类型和用户权限。权限失败立即返回明确错误，超时最多重试两次。用成功、无权限、超时三类测试检查回执与日志；这是课程演示，没有真实业务指标。'
      : '我做过简历里所述的订单 Agent，主要负责工具参数校验。具体失败恢复细节现在说不清楚。',
    scenario: '这是一个假设情境。我让模型选择允许的查询工具，程序检查订单编号、身份和权限后执行，再将真实结果回传。超时有限重试，权限失败停止，以成功、无权限和超时样例检查结果。',
    behavioral: '课程小组联调时字段不一致，我整理最小请求响应样例，与同学逐项确认后统一字段并补了失败样例。最终四个接口能对接，复盘后决定在编码前确认契约并安排早期联调。这是合成课程案例。',
    candidate_questions: '团队如何验证 Agent 工具调用的权限边界和失败恢复？新人如何获得代码审查与学习反馈？',
  };
  const answer = answers[turn.stage] ?? `关于本题“${turn.text}”，我目前不会解释具体机制和设计取舍，也没有相关实践，无法给出可靠细节。这是验收用的明确知识缺口回答。`;
  await page.getByRole('textbox', { name: '你的回答' }).fill(answer);
  await page.getByRole('button', { name: '提交回答', exact: true }).click();
  return { session_id: id, action: 'answer', stage: turn.stage, kind: turn.kind, question_code: turn.question_code, phase: (await read()).phase };
}
