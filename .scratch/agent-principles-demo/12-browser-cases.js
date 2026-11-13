// Playwright CLI, real HTTP and isolated acceptance database. Starts in the confirmed DOCX interview.
async (page) => {
  const cases = [];
  const readSession = async () => {
    const id = await page.evaluate(() => localStorage.getItem('ia-mi-session'));
    return (await (await page.request.get(new URL(`/api/v1/sessions/${id}`, page.url()).href)).json()).data;
  };
  const finish = async () => {
    await page.getByRole('button', { name: '结束面试', exact: true }).click();
    await page.getByRole('button', { name: '结束并生成报告', exact: true }).click();
    await page.getByRole('heading', { name: '部分面试报告', exact: true }).waitFor();
  };
  const back = async () => {
    await page.getByRole('button', { name: '返回模拟面试入口' }).click();
    await page.getByLabel('上传简历（可选）').waitFor();
  };
  const start = async () => {
    await page.getByRole('button', { name: '开始模拟面试', exact: true }).click();
    await page.getByRole('textbox', { name: '你的回答' }).waitFor();
  };
  const experience = async () => {
    await page.getByRole('button', { name: '跳过本轮', exact: true }).click();
    await page.getByRole('button', { name: '继续下一组', exact: true }).click();
    await page.getByRole('textbox', { name: '你的回答' }).waitFor();
    return readSession();
  };
  let session = await readSession();
  if (session.current_turn.stage !== 'experience' || !session.current_turn.text.includes('工具参数校验')) throw new Error('DOCX context missing');
  cases.push({ case: 'docx_confirmed', session_id: session.session_id, resume_id: session.resume_context.resume_id, stage: session.current_turn.stage });
  await finish();
  await page.getByText('本场项目陈述与来源', { exact: true }).click();
  await page.reload();
  await page.getByRole('heading', { name: '部分面试报告', exact: true }).waitFor();
  await page.getByText('本场项目陈述与来源', { exact: true }).click();
  await page.getByText('订单 Agent：我负责工具参数校验、权限检查和失败停止机制。', { exact: true }).waitFor();
  await back();

  await page.getByLabel('上传简历（可选）').setInputFiles('output/playwright/12-scanned.pdf');
  await page.getByText(/无法提取可用原文/).waitFor();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('alert').scrollIntoViewIfNeeded();
  await page.screenshot({ path: 'output/playwright/12-parse-fallback-mobile.png' });
  const corrected = '订单 Agent：我负责 FastAPI 入参校验和权限检查，使用失败停止机制。';
  await page.getByLabel('粘贴或修正项目文本').fill(corrected);
  await page.getByRole('button', { name: '预览项目文本', exact: true }).click();
  await page.getByRole('button', { name: '确认所选项目', exact: true }).click();
  await page.getByText('已确认，本场使用所选项目陈述。', { exact: true }).waitFor();
  await page.getByRole('button', { name: '修正所选项目文本', exact: true }).click();
  await page.getByLabel('粘贴或修正项目文本').fill(corrected + '结果以测试记录为准。');
  await page.getByRole('button', { name: '预览项目文本', exact: true }).click();
  await page.getByRole('button', { name: '确认所选项目', exact: true }).click();
  await page.getByText('已确认，本场使用所选项目陈述。', { exact: true }).waitFor();
  await start();
  session = await experience();
  if (!session.current_turn.text.includes('结果以测试记录为准') || session.resume_context.source_type !== 'pasted_text') throw new Error('Correction not used');
  cases.push({ case: 'scan_paste_correct_reconfirm', session_id: session.session_id, resume_id: session.resume_context.resume_id, stage: session.current_turn.stage });
  await page.getByText('本场项目陈述与来源', { exact: true }).click();
  await page.screenshot({ path: 'output/playwright/12-corrected-experience-mobile.png' });
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error('Mobile overflow');
  await finish(); await back();

  await page.getByLabel('上传简历（可选）').setInputFiles('output/playwright/12-resume.pdf');
  await page.getByRole('checkbox', { name: 'Order Agent: tool validation.' }).waitFor();
  await page.getByRole('button', { name: '确认所选项目', exact: true }).click();
  await page.getByText('已确认，本场使用所选项目陈述。', { exact: true }).waitFor();
  await start();
  session = await readSession();
  if (session.resume_context.source_type !== 'pdf' || session.resume_context.projects[0].source.page !== 1) throw new Error('PDF source missing');
  cases.push({ case: 'pdf_upload_confirm', session_id: session.session_id, resume_id: session.resume_context.resume_id, source: session.resume_context.projects[0].source });
  await finish(); await back();

  await start(); session = await experience();
  if (session.resume_context || session.current_turn.stage !== 'scenario') throw new Error('Unexpected resume or no scenario');
  cases.push({ case: 'no_resume_direct', session_id: session.session_id, stage: session.current_turn.stage, text: session.current_turn.text });
  await finish(); await back();

  await page.getByRole('button', { name: '确认没有相关项目经历', exact: true }).click();
  await page.getByText('已确认没有相关项目经历，本场使用假设情境题。', { exact: true }).waitFor();
  await start(); session = await experience();
  if (!session.resume_context.no_project_experience || session.current_turn.stage !== 'scenario') throw new Error('No-project branch failed');
  cases.push({ case: 'explicit_no_projects', session_id: session.session_id, resume_id: session.resume_context.resume_id, stage: session.current_turn.stage });
  await page.getByText('本场项目陈述与来源', { exact: true }).click();
  await page.screenshot({ path: 'output/playwright/12-no-projects-mobile.png' });
  await finish();
  return cases;
}
