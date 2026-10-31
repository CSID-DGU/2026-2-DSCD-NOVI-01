import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppHeader from '../../components/AppHeader/AppHeader.jsx'
import FeatureCard from '../../components/FeatureCard/FeatureCard.jsx'
import UploadOption from '../../components/UploadOption/UploadOption.jsx'
import ArrowCircle from '../../components/ui/ArrowCircle.jsx'
import './HomePage.css'
import WorksSection from '../../components/WorksSection/WorksSection.jsx'

/** 05_Home.svg - 서비스 메인 */
export default function HomePage() {
  const navigate = useNavigate()
  const cameraRef = useRef(null)
  const fileRef = useRef(null)
  const [selectedFile, setSelectedFile] = useState(null)
  const [fileMessage, setFileMessage] = useState('')

  function handleFileChange(event) {
    const file = event.target.files?.[0]
    // 같은 파일을 다시 선택할 수 있도록 입력 값 초기화
    event.target.value = ''
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setFileMessage('티켓 이미지 파일을 선택해 주세요.')
      setSelectedFile(null)
      return
    }
    setSelectedFile(file)
    setFileMessage('')
  }

  return (
    <div className="tt-home-page">
      <AppHeader />
      <main className="tt-home-main" aria-label="TicketTaka 메인">
        <div className="tt-home-main__left">
          <FeatureCard
            number="01" label="추천" title="Today's Picks"
            description="당신의 취향에서 시작되는 추천"
            tags={['뮤지컬', '콘서트', '전시', '영화']}
            to="/picks" variant="blue"
          />
          <FeatureCard
            number="02" label="기록" title="My Tickets"
            description="지나온 문화생활을 모아보세요"
            to="/tickets" variant="lavender"
          />
        </div>

        <section className="tt-home-upload" aria-labelledby="tt-home-upload-title">
          <div className="tt-home-upload__heading">
            <div>
              <span className="tt-home-upload__eyebrow">03 · 업로드</span>
              <h1 id="tt-home-upload-title">Upload Ticket</h1>
              <p>한 장의 티켓에 경험을 담아보세요</p>
            </div>
            <ArrowCircle to="/upload" label="티켓 업로드 페이지로 이동" variant="lavender" />
          </div>

          <div className="tt-home-upload__options">
            <UploadOption type="camera" title="티켓 사진"
              description={'카메라로 티켓을 찍으면\n정보를 자동으로 읽어요'}
              buttonText="촬영하기" emphasized
              onClick={() => cameraRef.current?.click()}
            />
            <UploadOption type="image" title="이미지 첨부"
              description={'저장된 티켓·예매 내역\n이미지를 올려 읽어요'}
              buttonText="파일 선택"
              onClick={() => fileRef.current?.click()}
            />
            <UploadOption type="pencil" title="수기 입력"
              description={'티켓이 없어도 작품을\n검색해 직접 기록해요'}
              buttonText="직접 입력"
              onClick={() => navigate('/upload/manual')}
            />
          </div>

          {/* 카메라/파일 선택은 브라우저에서 실행. 실제 업로드·OCR은 추후 업로드 페이지에 연동. */}
          <input ref={cameraRef} className="tt-home-upload__hidden-input" type="file" accept="image/*" capture="environment" onChange={handleFileChange} aria-label="카메라로 티켓 촬영" />
          <input ref={fileRef} className="tt-home-upload__hidden-input" type="file" accept="image/*" onChange={handleFileChange} aria-label="티켓 이미지 선택" />
          <div className="tt-home-upload__footer" aria-live="polite">
            {selectedFile ? (
              <div className="tt-home-upload__selected">
                <span>선택한 이미지: <strong>{selectedFile.name}</strong> · 아직 업로드되지 않았어요.</span>
                <button type="button" onClick={() => setSelectedFile(null)}>선택 취소</button>
              </div>
            ) : fileMessage ? (
              <span role="alert">{fileMessage}</span>
            ) : (
              <span>인식된 정보는 등록 전에 직접 확인하고 고칠 수 있어요</span>
            )}
          </div>
        </section>
      </main>

      {/* 실제 작품 DB 목록 */}
      <WorksSection />

    </div>
  )
}