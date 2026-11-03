import { useNavigate } from 'react-router-dom'
import TicketResultPage from './TicketResultPage.jsx'
import { registerLocalTicket } from '../../api/myTickets.js'
/**
 * 기존 TicketResultPage의 onRegister로 My Tickets 브라우저 데모 저장소에 연결.
 * 실제 DB 저장이 아니라는 점을 My Tickets에서 표시합니다.
 */
export default function TicketLocalRegisterRoute({ manual = false }) {
  const navigate = useNavigate()
  const onRegister = async (payload) => {
    registerLocalTicket(payload)
    navigate('/tickets', { replace: true })
  }
  return <TicketResultPage manual={manual} onRegister={onRegister}/>
}
