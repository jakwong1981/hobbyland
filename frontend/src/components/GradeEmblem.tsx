// frontend/src/components/GradeEmblem.tsx
import type { Grade } from '../types';

// Purely decorative: the grade name is always rendered as text next to it.
export function GradeEmblem({ grade }: { grade: Grade }) {
  return (
    <svg className="grade-emblem" data-grade={grade} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <polygon className="grade-emblem-outer" points="8,0.8 15.2,8 8,15.2 0.8,8" />
      <polygon className="grade-emblem-inner" points="8,4.6 11.4,8 8,11.4 4.6,8" />
    </svg>
  );
}
