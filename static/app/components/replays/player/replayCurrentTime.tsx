import {useState} from 'react';

import {DateTime} from 'sentry/components/dateTime';
import Duration from 'sentry/components/duration/duration';
import {useReplayContext} from 'sentry/components/replays/replayContext';
import useReplayCurrentTime from 'sentry/utils/replays/playback/hooks/useReplayCurrentTime';
import {useReplayPrefs} from 'sentry/utils/replays/playback/providers/replayPreferencesContext';
import {useReplayReader} from 'sentry/utils/replays/playback/providers/replayReaderProvider';
import useOrganization from 'sentry/utils/useOrganization';

export default function ReplayCurrentTime() {
  const organization = useOrganization();
  if (organization.features.includes('replay-new-context')) {
    return <ReplayCurrentTimeNew />;
  }

  return <OriginalReplayCurrentTime />;
}

function ReplayCurrentTimeNew() {
  const [prefs] = useReplayPrefs();
  const replay = useReplayReader();
  const [currentTime, setCurrentTime] = useState({timeMs: 0});

  useReplayCurrentTime({callback: setCurrentTime});

  switch (prefs.timestampType) {
    case 'absolute': {
      const startTimestamp = replay?.getStartTimestampMs() ?? 0;
      return <DateTime date={currentTime.timeMs + startTimestamp} seconds timeOnly />;
    }
    case 'relative':
    default:
      return <Duration duration={[currentTime.timeMs, 'ms']} precision="sec" />;
  }
}

function OriginalReplayCurrentTime() {
  const replay = useReplayReader();
  const {currentTime} = useReplayContext();
  const [prefs] = useReplayPrefs();
  const timestampType = prefs.timestampType;
  const startTimestamp = replay?.getStartTimestampMs() ?? 0;

  return timestampType === 'absolute' ? (
    <DateTime timeOnly seconds date={startTimestamp + currentTime} />
  ) : (
    <Duration duration={[currentTime, 'ms']} precision="sec" />
  );
}
