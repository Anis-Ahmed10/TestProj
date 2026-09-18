export interface SanitizationRule {
  name: string;
  pattern: RegExp;
  replacement: string;
}

export interface SanitizableStory {
  storyTitle?: string;
  description?: string;
  acceptanceCriteria?: string[];
}

export interface SanitizableEpic<
  StoryShape extends SanitizableStory = SanitizableStory,
> {
  epicTitle?: string;
  stories?: StoryShape[];
}

export type SanitizableEpicEntry<
  EpicShape extends SanitizableEpic = SanitizableEpic,
> = Record<string, EpicShape>;

export type SanitizableEpicsPayload<
  EpicShape extends SanitizableEpic = SanitizableEpic,
> = SanitizableEpicEntry<EpicShape>[];
