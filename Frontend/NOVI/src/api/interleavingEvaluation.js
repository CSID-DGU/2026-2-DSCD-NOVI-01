import { apiRequest } from './auth.js'

// 브라우저에는 모델 출처가 포함되지 않은 노출 작품만 내려온다.
// NOVI/GPT 원본 추천과 매칭한 정보는 Django EvaluationSession에 보관한다.
export function getEvaluationContext({ signal } = {}) {
  return apiRequest('/api/evaluations/context', { signal })
}

// Django가 GPT 생성 및 검증까지 직접 실행하므로 클라이언트가 GPT 결과를 전달하지 않습니다.
export function startEvaluation({ signal } = {}) {
  return apiRequest('/api/evaluations/start', {
    method: 'POST', body: {}, signal,
  })
}

export function submitEvaluation(sessionId, selections) {
  return apiRequest(`/api/evaluations/${encodeURIComponent(sessionId)}/submit`, {
    method: 'POST',
    body: { selections: selections.map(({ category, item_id }) => ({ category, item_id })) },
  })
}

export function getEvaluationResults() {
  return apiRequest('/api/evaluations/results')
}
