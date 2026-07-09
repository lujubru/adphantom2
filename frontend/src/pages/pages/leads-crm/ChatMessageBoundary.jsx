import React from 'react';

/**
 * Error boundary for a single chat message. If one message throws while
 * rendering (e.g. malformed receipt_data), we still want the rest of the
 * chat to be usable instead of a full blank screen. Falls back to a small
 * inline placeholder so the cajero can see something is wrong.
 */
export class ChatMessageBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { crashed: false };
  }

  static getDerivedStateFromError() {
    return { crashed: true };
  }

  componentDidCatch(err, info) {
    // eslint-disable-next-line no-console
    console.error('[ChatMessage] render error', err, info);
  }

  render() {
    if (this.state.crashed) {
      return (
        <div
          className="flex justify-center my-1"
          data-testid={`msg-crashed-${this.props.messageId || ''}`}
        >
          <div className="max-w-[70%] px-2 py-1 rounded-md bg-red-500/10 border border-red-500/30 text-red-200 text-[10px]">
            No se pudo mostrar este mensaje.
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
