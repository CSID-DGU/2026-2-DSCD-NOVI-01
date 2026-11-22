import { apiRequest } from './auth.js'

const OCR_ENDPOINT = import.meta.env.VITE_OCR_API_PATH || '/api/tickets/ocr/'
const MAX_IMAGE_BYTES = 10 * 1024 * 1024

/** 백엔드 OCR은 DB에 저장하지 않고 확인용 초안만 반환합니다. */
export async function recognizeTicketImage(file, signal) {
  if (!(file instanceof File) || !file.type.startsWith('image/')) {
    throw new Error('티켓 이미지 파일을 선택해 주세요.')
  }
  if (file.size > MAX_IMAGE_BYTES) {
    throw new Error('이미지는 10MB 이하만 올릴 수 있어요.')
  }

  const form = new FormData()
  form.append('image', file, file.name)
  const result = await apiRequest(OCR_ENDPOINT, { method: 'POST', body: form, signal })
  if (!Array.isArray(result?.drafts)) {
    throw new Error('OCR 서버 응답 형식이 올바르지 않아요. (drafts 배열 없음)')
  }
  return result
}
