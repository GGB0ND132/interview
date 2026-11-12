// Run with playwright-cli run-code --filename. Synthetic candidate answers only.
async (page) => {
  const sessionId = await page.evaluate(() => localStorage.getItem('ia-mi-session'));
  if (!sessionId) throw new Error('Start the interview through the browser first');
  const read = async () => (await (await page.request.get(new URL(`/api/v1/sessions/${sessionId}`, page.url()).href)).json()).data;
  let session = await read();
  if (session.status === 'completed' || session.status === 'ended_early') {
    await page.getByRole('heading', { name: /面试报告/ }).waitFor();
    return { session_id: sessionId, status: session.status, report_visible: true };
  }
  if (session.phase === 'stage_transition') {
    await page.getByRole('button', { name: '继续下一组' }).click();
    await page.getByRole('textbox', { name: '你的回答' }).waitFor();
    session = await read();
  }
  const answers = {
    introduction: '我是一名计算机专业学生，最近学习 Agent 的工具调用和执行循环，做过课程中的订单查询练习。我负责接口参数校验和失败记录，希望学习如何把模型能力接入可靠的业务流程。',
    scenario: '在这个假设情境中，我让模型理解请求、选择允许的查询工具和组织参数。程序校验订单编号、用户身份和订单访问权限，执行查询后把真实结果或结构化错误返回模型，再由模型解释。权限失败立即停止，网络超时有限重试，设置最多三轮和总超时。分别测试成功、无权限、订单不存在、超时，核对结果和日志，避免越权或无限循环。',
    behavioral: '课程小组整合接口时，大家使用的字段名不一致，联调失败。我整理最小请求响应样例，和同学逐项确认，再统一字段并补充失败样例。最终四个接口都能对接；复盘发现沟通太晚，下次在编码前一起确定契约，再安排早期联调。',
    candidate_questions: '团队如何验证 Agent 工具调用的失败恢复和权限边界？新人会从哪些场景入手，如何获得代码审查和反馈？',
    'Q-2659': 'Tool 是 Agent 访问外部能力的接口，例如数据库查询、搜索和业务 API。工具定义包含名称、用途、参数结构；模型根据任务选择工具并给参数，实际执行由程序完成。程序需要验证参数和权限，执行后把真实结果或错误交回模型。工具可以只读也可以有副作用，写操作要考虑确认、幂等和审计；失败需要明确回执与有限重试，不能把模型提出调用当作执行成功。',
    'Q-7196': '先计算输入和输出的 token 预算，预留输出空间。对长历史可保留近期轮次和关键事实，删除重复或无关内容，摘要压缩旧对话；对长文档可按结构切块并检索当前问题相关片段，或分块处理后汇总。还可以选择更长窗口模型，但费用与延迟会增加，长窗口也不能保证关键内容被正确使用。工具输出要筛选，不能截断到丢失用户目标、约束、引用来源或未完成事项，摘要和检索都要验证信息损失。',
    'Q-3642': '记忆系统中的意图识别先理解当前请求要完成什么任务，判断哪些信息需要读取、哪些值得保存或更新。比如用户说明饮食偏好是长期资料更新，而询问某订单进度主要需要当前订单上下文。识别后据意图选择记忆类型、检索范围、触发查询或写入，避免把无关历史全部塞给模型。它不是记忆存储本身，也不能单独保证检索准确，需要结合权限、时效、置信度和用户确认，意图不确定时先澄清。',
    'Q-0898': 'Coding Agent 是以大模型为决策核心、能围绕软件任务多步使用工具并根据反馈继续工作的编码智能体。它读取代码和项目约定，制定计划，编辑文件，调用终端、构建和测试，再依据报错修正，最后交付可审查的变更。它区别于只提供补全或单次生成代码的助手。模型提出动作，运行环境实际执行并记录状态；需要限制文件和命令权限、执行预算，保护密钥，对危险操作确认。通过测试、差异审查和人工验收判断结果，不把生成了代码当作任务已完成。',
  };
  if (session.phase === 'evaluation_failed') {
    await page.getByRole('button', { name: '重试评价' }).click();
    await page.getByRole('button', { name: '重试评价' }).waitFor({ state: 'hidden' });
  } else if (session.phase === 'awaiting_answer') {
    const answer = answers[session.current_turn.question_code] || answers[session.current_turn.stage];
    if (!answer) throw new Error(`No synthetic fixture for ${session.current_turn.question_code}`);
    if (await page.getByText('查看参考答案', { exact: true }).count()) throw new Error('Reference answer exposed during interview');
    await page.getByRole('textbox', { name: '你的回答' }).fill(answer);
    await page.getByRole('button', { name: '提交回答', exact: true }).click();
    await page.getByRole('button', { name: '提交回答', exact: true }).waitFor({ state: 'hidden' });
  }
  // Wait on visible state, never advance by elapsed time.
  await page.getByRole('button', { name: /继续下一组|重试评价/ }).or(page.getByRole('heading', { name: /面试报告/ })).or(page.getByRole('textbox', { name: '你的回答' })).first().waitFor({ timeout: 60000 });
  const updated = await read();
  return { session_id: sessionId, stage: session.current_turn.stage, kind: session.current_turn.kind, question_code: session.current_turn.question_code, phase: updated.phase, status: updated.status, revision: updated.revision, turns: updated.turns.length };
}
