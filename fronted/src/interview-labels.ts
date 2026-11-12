import type { Coverage, Dimension, Disposition, InterviewStage, PlannedQuestion } from './api'

export const STAGES: Record<InterviewStage, string> = { introduction: '开场', experience: '项目与经历', scenario: '假设情境', technical: '技术交流', behavioral: '行为交流', candidate_questions: '候选人反问' }
export const COVERAGE: Record<Coverage['status'], string> = { unobserved: '待了解', insufficient: '信息不足', observed: '已了解', not_applicable: '不适用' }
export const DIMENSIONS: Record<Dimension['name'], string> = { accuracy: '准确性', completeness: '完整性', relevance: '相关性', structure: '表达结构', specificity: '具体性' }
export const DISPOSITIONS: Record<Disposition, string> = { answered: '', blank_answer: '空白提交', skipped: '已跳过，不计分', no_experience: '没有项目经历', no_questions: '没有问题' }

const AGENT_TOPICS: Record<string, string> = {
  agent_loop: 'Agent 基础与运行循环', agent_application_architecture: 'Agent 应用架构与场景设计',
  agent_planning: '规划、推理与任务执行', agent_context_engineering: '上下文工程',
  agent_memory: '记忆系统', agent_tool_calling: '工具调用与 Function Calling',
  agent_protocols: 'MCP、A2A 与工具协议', agent_skills: 'Skills 能力系统',
  agent_workflow_recovery: '工作流、状态与执行恢复', agent_multi_agent: '多 Agent 编排与协作',
  agent_frameworks_harness: 'Agent 框架与 Harness', agent_gui: 'GUI、Computer Use 与多模态 Agent',
}

export function competencyLabel(id: string, questions: PlannedQuestion[]) {
  return STAGES[id as InterviewStage] ?? questions.find(question => question.competency_id === id)?.topic ?? AGENT_TOPICS[id] ?? id
}
