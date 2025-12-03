import { LiveEventItem } from './LiveEventItem';
import type { LiveEvent } from '@/types/api';

interface LiveEventListProps {
  events: LiveEvent[];
  newEventIds?: Set<string>;
}

export function LiveEventList({ events, newEventIds = new Set() }: LiveEventListProps) {
  if (events.length === 0) {
    return (
      <div className="card-glass rounded-xl p-8 text-center">
        <p className="text-muted-foreground">No events to display</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {events.map((event) => (
        <LiveEventItem 
          key={event.id} 
          event={event} 
          isNew={newEventIds.has(event.id)}
        />
      ))}
    </div>
  );
}
