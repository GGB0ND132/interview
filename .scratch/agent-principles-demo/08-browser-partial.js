// A separate live browser case: pause, skip, no project, focused follow-up, early end.
async (page) => {
  await page.getByRole('button', { name: '返回模拟面试入口' }).click();
  await page.getByRole('combobox', { name: '经历环节' }).selectOption('experience');
  await page.getByRole('button', { name: '开始模拟面试' }).click();
  const input = page.getByRole('textbox', { name: '你的回答' });
  await input.fill('这段未提交草稿用于验证暂停后保留。');
  await page.getByRole('button', { name: '暂停面试' }).click();
  if (!await input.isDisabled()) throw new Error('Pause did not lock the composer');
  await page.getByRole('button', { name: '继续面试', exact: true }).click();
  if (await input.inputValue() !== '这段未提交草稿用于验证暂停后保留。') throw new Error('Draft lost on pause');
  await page.getByRole('button', { name: '跳过本轮' }).click();
  await page.getByRole('button', { name: '继续下一组' }).click();
  await page.getByRole('button', { name: '没有项目经历' }).click();
  await page.getByRole('button', { name: '继续下一组' }).click();
  await page.getByText(/【假设情境，并非你的真实经历】/).waitFor();
  await input.fill('我大概知道，应该调用一下就可以了，具体流程说不清。');
  await page.getByRole('button', { name: '提交回答', exact: true }).click();
  await page.getByRole('button', { name: '提交回答', exact: true }).waitFor({ state: 'hidden' });
  await page.locator('.practice-scroll').hover();
  await page.mouse.wheel(0, -2000);
  await input.or(page.getByRole('button', { name: /继续下一组|重试评价/ })).first().waitFor({ timeout: 60000 });
  const sessionId = await page.evaluate(() => localStorage.getItem('ia-mi-session'));
  const response = await page.request.get(new URL(`/api/v1/sessions/${sessionId}`, page.url()).href);
  const session = (await response.json()).data;
  const unread = await page.getByRole('button', { name: '有新的交流，跳转到最新位置' }).isVisible();
  if (session.current_turn.kind === 'followup' && !unread) throw new Error('New follow-up pulled the reader from old answers');
  if (unread) await page.getByRole('button', { name: '有新的交流，跳转到最新位置' }).click();
  await page.getByRole('button', { name: '结束面试', exact: true }).click();
  await page.getByRole('button', { name: '结束并生成报告' }).click();
  await page.getByRole('heading', { name: '部分面试报告' }).waitFor();
  return { session_id: sessionId, pause_preserved_draft: true, skipped_opening: true, no_experience_to_scenario: true, returned_kind: session.current_turn.kind, prompt: session.current_turn.text, reading_position_preserved: unread, partial_report_visible: true };
}
