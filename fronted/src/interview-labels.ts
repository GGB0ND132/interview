import type { Coverage, Dimension, Disposition, InterviewStage, PlannedQuestion } from './api'

export const STAGES: Record<InterviewStage, string> = { introduction: '开场', experience: '项目与经历', scenario: '假设情境', technical: '技术交流', behavioral: '行为交流', candidate_questions: '候选人反问' }
export const COVERAGE: Record<Coverage['status'], string> = { unobserved: '待了解', insufficient: '信息不足', observed: '已了解', not_applicable: '不适用' }
export const DIMENSIONS: Record<Dimension['name'], string> = { accuracy: '准确性', completeness: '完整性', relevance: '相关性', structure: '表达结构', specificity: '具体性' }
export const DISPOSITIONS: Record<Disposition, string> = { answered: '', blank_answer: '空白提交', skipped: '已跳过，不计分', no_experience: '没有项目经历', no_questions: '没有问题' }

export function competencyLabel(id: string, questions: PlannedQuestion[]) {
  return questions.find(question => question.competency_id === id)?.topic ?? STAGES[id as InterviewStage] ?? id
}
