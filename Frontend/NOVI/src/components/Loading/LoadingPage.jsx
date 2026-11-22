import './LoadingPage.css';
import PropTypes from 'prop-types';

export default function LoadingPage({
  message = '취향을 분석하고 있어요',
  subMessage = '잠시만 기다려 주세요',
}) {
  return (
    <div className="tt-loading" role="status" aria-live="polite">
      <div className="tt-loading__ticket" aria-hidden="true">
        <span className="tt-loading__stub" />
        <span className="tt-loading__bar" />
      </div>

      <p className="tt-loading__message">{message}</p>
      <p className="tt-loading__sub">{subMessage}</p>

      <div className="tt-loading__dots" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}

LoadingPage.propTypes = {
  message: PropTypes.string,
  subMessage: PropTypes.string,
};