// Component that sets up event stream and displays notifications
import { useEventStream } from '../hooks';
import { useToast } from './notifications';
import type { ReactNode } from 'react';

interface EventData {
  type: string;
  [key: string]: unknown;
}

export function EventStreamSetup({ children }: { children: ReactNode }) {
  const { info, warning, success, error: showError } = useToast();

  useEventStream({
    onEvent: (event) => {
      if (event.type === 'ping') {
        // Silently handle pings
        return;
      }

      try {
        const eventData = event.data as EventData;

        // Route events to appropriate toast based on event type
        if (eventData.type === 'error') {
          const message = typeof eventData.message === 'string' ? eventData.message : 'An error occurred';
          showError(message);
        } else if (eventData.type === 'warning') {
          const message = typeof eventData.message === 'string' ? eventData.message : 'Warning';
          warning(message);
        } else if (eventData.type === 'success') {
          const message = typeof eventData.message === 'string' ? eventData.message : 'Success';
          success(message);
        } else {
          // Default to info for other types
          const message = typeof eventData.message === 'string' ? eventData.message : `Event: ${eventData.type}`;
          info(message);
        }
      } catch (err) {
        // Log but don't crash on malformed events
        console.error('Failed to process event:', err);
      }
    },
    onError: (error) => {
      // Only show error if it's not a normal disconnect
      if (error.message !== 'EventSource connection lost') {
        showError(`Connection error: ${error.message}`);
      }
    },
  });

  return <>{children}</>;
}
