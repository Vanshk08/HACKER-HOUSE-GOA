import { request } from './client';

export async function fetchCases() {
  return request('/api/cases');
}

export async function fetchCase(caseId) {
  return request(`/api/cases/${encodeURIComponent(caseId)}`);
}

export async function startInvestigation(caseId, provider = null) {
  return request('/api/investigate', {
    method: 'POST',
    body: JSON.stringify({ case_id: caseId, provider }),
  });
}

export function subscribeInvestigationStream(caseId, onMessage, onError, onComplete) {
  const url = `/api/investigate/stream/${encodeURIComponent(caseId)}`;
  const eventSource = new EventSource(url);

  let completed = false;
  let receivedData = false;

  const handleEvent = (type, e) => {
    try {
      const data = JSON.parse(e.data);
      receivedData = true;
      onMessage({ type, data });
    } catch (err) {
      console.error(`SSE ${type} parse error:`, err);
    }
  };

  eventSource.addEventListener('case_loaded', (e) => {
    handleEvent('case_loaded', e);
  });

  eventSource.addEventListener('tool_execution', (e) => {
    handleEvent('tool_execution', e);
  });

  eventSource.addEventListener('assessment', (e) => {
    handleEvent('assessment', e);
  });

  eventSource.addEventListener('policy', (e) => {
    handleEvent('policy', e);
  });

  eventSource.addEventListener('complete', (e) => {
    try {
      const data = JSON.parse(e.data);
      receivedData = true;
      completed = true;

      onMessage({ type: 'complete', data });

      if (onComplete) {
        onComplete(data);
      }
    } catch (err) {
      console.error('SSE complete parse error:', err);
    } finally {
      eventSource.close();
    }
  });

  eventSource.onerror = (err) => {
    // If the complete event was received, this is just the connection
    // closing after a successful investigation.
    if (completed) {
      eventSource.close();
      return;
    }

    // Don't immediately close/retry through the synchronous endpoint
    // if we've already received valid investigation events.
    if (receivedData) {
      console.warn('SSE connection interrupted after receiving data:', err);
      return;
    }

    if (onError) {
      onError(err);
    }

    eventSource.close();
  };

  return () => {
    completed = true;
    eventSource.close();
  };
}