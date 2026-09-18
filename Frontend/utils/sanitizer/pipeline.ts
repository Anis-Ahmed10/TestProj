import { createBasicRegexLayer } from "./basicRegexLayer";
import { withSanitizationErrorContext } from "./sanitizer";
import { createUniversityKeywordsLayer } from "./university/UniversityKeywordsLayer";
import type {
  SanitizableEpic,
  SanitizableEpicEntry,
  SanitizableEpicsPayload,
  SanitizableStory,
} from "../../types/sanitizer_types";

const basicLayer = createBasicRegexLayer();
type SanitizationLayer = {
  sanitizeText(value: string): string;
};

export type OptionalSanitizationLayerName = "university";

const optionalLayerFactories: Record<
  OptionalSanitizationLayerName,
  () => SanitizationLayer
> = {
  university: () => createUniversityKeywordsLayer(),
};

const initializedOptionalLayers = new Map<
  OptionalSanitizationLayerName,
  SanitizationLayer
>();

function sanitizeString(text: string): string {
  let sanitized = basicLayer.sanitizeText(text);

  for (const layer of initializedOptionalLayers.values()) {
    sanitized = layer.sanitizeText(sanitized);
  }

  return sanitized;
}

export function initializeSanitizationLayer(
  layerName: OptionalSanitizationLayerName,
): void {
  if (initializedOptionalLayers.has(layerName)) {
    return;
  }

  initializedOptionalLayers.set(layerName, optionalLayerFactories[layerName]());
}

export function initializeSanitizationLayers(
  layerNames: OptionalSanitizationLayerName[],
): void {
  for (const layerName of layerNames) {
    initializeSanitizationLayer(layerName);
  }
}

export function initializeUniversitySanitizer(): void {
  initializeSanitizationLayer("university");
}

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function validateSanitizableEpicsPayload<EpicShape extends SanitizableEpic>(
  input: SanitizableEpicsPayload<EpicShape>,
): void {
  if (!Array.isArray(input)) {
    throw new TypeError(
      "Invalid epics payload: expected an array of epic wrapper objects.",
    );
  }

  input.forEach((entry, entryIndex) => {
    if (!isObjectRecord(entry)) {
      throw new Error(
        `Invalid epics payload at index ${entryIndex}: expected an object with a single epic key.`,
      );
    }

    const entryKeys = Object.keys(entry);

    if (entryKeys.length !== 1) {
      throw new Error(
        `Invalid epics payload at index ${entryIndex}: expected exactly one epic key, received ${entryKeys.length}.`,
      );
    }

    const [epicKey] = entryKeys;
    const epicValue = entry[epicKey];

    if (!isObjectRecord(epicValue)) {
      throw new Error(
        `Invalid epics payload at index ${entryIndex}: epic "${epicKey}" must map to an object.`,
      );
    }

    if (!Array.isArray(epicValue.stories)) {
      throw new TypeError(
        `Invalid epics payload at index ${entryIndex}: epic "${epicKey}" must include a stories array.`,
      );
    }
  });
}

function sanitizeAcceptanceCriteria(
  value: string[] | undefined,
): string[] | undefined {
  return value?.map((criterion) => sanitizeString(criterion));
}

function sanitizeStoryFields<StoryShape extends SanitizableStory>(
  story: StoryShape,
): StoryShape {
  const sanitizedStory = { ...story };

  if (typeof sanitizedStory.storyTitle === "string") {
    sanitizedStory.storyTitle = sanitizeString(sanitizedStory.storyTitle);
  }

  if (typeof sanitizedStory.description === "string") {
    sanitizedStory.description = sanitizeString(sanitizedStory.description);
  }

  if (Array.isArray(sanitizedStory.acceptanceCriteria)) {
    sanitizedStory.acceptanceCriteria = sanitizeAcceptanceCriteria(
      sanitizedStory.acceptanceCriteria,
    );
  }

  return sanitizedStory;
}

function sanitizeEpicFields<EpicShape extends SanitizableEpic>(
  epic: EpicShape,
): EpicShape {
  const sanitizedEpic = { ...epic };

  if (typeof sanitizedEpic.epicTitle === "string") {
    sanitizedEpic.epicTitle = sanitizeString(sanitizedEpic.epicTitle);
  }

  if (Array.isArray(sanitizedEpic.stories)) {
    sanitizedEpic.stories = sanitizedEpic.stories.map((story) =>
      sanitizeStoryFields(story),
    );
  }

  return sanitizedEpic;
}

function sanitizeEpicEntry<EpicShape extends SanitizableEpic>(
  epicEntry: SanitizableEpicEntry<EpicShape>,
): SanitizableEpicEntry<EpicShape> {
  return Object.fromEntries(
    Object.entries(epicEntry).map(([epicKey, epicValue]) => [
      epicKey,
      sanitizeEpicFields(epicValue),
    ]),
  ) as SanitizableEpicEntry<EpicShape>;
}

function sanitizeSelectedEpicFields<EpicShape extends SanitizableEpic>(
  value: SanitizableEpicsPayload<EpicShape>,
): SanitizableEpicsPayload<EpicShape> {
  return value.map((epicEntry) => sanitizeEpicEntry(epicEntry));
}

export function sanitizeEpicsPayload<EpicShape extends SanitizableEpic>(
  input: SanitizableEpicsPayload<EpicShape>,
): SanitizableEpicsPayload<EpicShape> {
  return withSanitizationErrorContext("sanitize epics payload", () => {
    validateSanitizableEpicsPayload(input);
    return sanitizeSelectedEpicFields(input);
  });
}
