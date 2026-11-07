export type LoadingWorkflow = "story" | "characters" | "scenes" | "narration" | "render";

export const loadingMessages: Record<string, Record<LoadingWorkflow, readonly string[]>> = {
  en: {
    story: [
      "Convincing characters to cooperate...", "Negotiating plot twists...", "Consulting the storytelling department...",
      "Untangling the third act...", "Asking the plot to thicken...", "Giving foreshadowing a subtle nudge...",
      "Checking the hero's calendar...", "Removing accidental cliffhangers...", "Interviewing suspicious side characters...",
      "Keeping the ending under wraps...", "Organizing a meeting with destiny...", "Rehearsing a very important revelation...",
      "Looking for the missing motivation...", "Persuading the premise to make sense...", "Giving the story a spine...",
      "Connecting dots with dramatic string...", "Putting the twist through quality control...", "Finding a purpose for the mysterious key...",
      "Making sure act two shows up...", "Asking coincidence to take a day off...",
    ],
    characters: [
      "Choosing dramatic haircuts...", "Teaching heroes how to pose...", "Preventing villains from stealing the spotlight...",
      "Checking everyone's wardrobe continuity...", "Assigning memorable eyebrows...", "Matching boots to backstories...",
      "Getting the protagonist's good side...", "Politely declining extra capes...", "Saving a seat for the sidekick...",
      "Making the villain sign the call sheet...", "Checking that scars stay on the same cheek...", "Keeping hats from changing careers...",
      "Finding the character's favorite jacket...", "Teaching the ensemble to stand still...", "Scheduling a fictional costume fitting...",
      "Asking the hero not to blink...", "Giving extras their personal space...", "Resolving a disagreement about mustaches...",
      "Keeping eye colors out of the lottery...", "Making the reference portrait feel appreciated...",
    ],
    scenes: [
      "Scouting fictional locations...", "Checking imaginary weather forecasts...", "Coordinating camera crews...",
      "Putting mountains in their assigned places...", "Asking the sun for softer lighting...", "Making clouds sign a continuity form...",
      "Sweeping stray pixels off the set...", "Finding the camera's imaginary lens cap...", "Keeping doors in the same wall...",
      "Sending a map to the next scene...", "Preventing the ocean from moving inland...", "Checking the imaginary horizon...",
      "Making props remember their positions...", "Negotiating with dramatic fog...", "Rolling out a fictional red carpet...",
      "Keeping shadows pointed the right way...", "Giving the background a pep talk...", "Filing a permit for this sunset...",
      "Making sure the moon is not an extra...", "Asking locations to respect the script...",
    ],
    narration: [
      "Teaching the narrator how to breathe...", "Removing excessive dramatic pauses...", "Making the narrator sound awake...",
      "Connecting sentences with narrative glue...", "Warming up imaginary vocal cords...", "Asking commas to take a short break...",
      "Getting the bridge to the next scene ready...", "Making pronouns introduce themselves...", "Checking the narrator's story notes...",
      "Turning down unnecessary suspense...", "Giving the opening line some confidence...", "Keeping the ending from arriving early...",
      "Asking the story to use its indoor voice...", "Making transitions mind the gap...", "Counting breaths, not sheep...",
      "Keeping the narrator on the same page...", "Finding a smoother way to say meanwhile...", "Checking the pronunciation of destiny...",
      "Making every sentence earn its microphone...", "Offering the narrator a fictional glass of water...",
    ],
    render: [
      "Polishing pixels...", "Aligning cinematic particles...", "Convincing frames to work together...",
      "Teaching transitions to be smooth...", "Giving the timeline a final comb...", "Packing frames into an MP4 suitcase...",
      "Making audio and pictures shake hands...", "Checking the pixels' attendance...", "Ironing out cinematic wrinkles...",
      "Making fades leave gracefully...", "Asking the encoder for its best work...", "Keeping camera moves on their marks...",
      "Sending jitter to the editing room...", "Counting frames without losing the plot...", "Giving the export a window seat...",
      "Putting the final cut in a safe container...", "Checking that every scene made the bus...", "Keeping the soundtrack on schedule...",
      "Assembling a tiny film festival...", "Making the download worth the wait...",
    ],
  },
};

export class LoadingMessageService {
  private remaining: string[] = [];
  private last = "";
  constructor(private messages: readonly string[], private random: () => number = Math.random) {
    if (new Set(messages).size < 20) throw new Error("A workflow requires at least 20 unique loading messages.");
  }
  next(): string {
    if (!this.remaining.length) {
      this.remaining = [...new Set(this.messages)];
      for (let index = this.remaining.length - 1; index > 0; index--) {
        const other = Math.floor(this.random() * (index + 1));
        [this.remaining[index], this.remaining[other]] = [this.remaining[other], this.remaining[index]];
      }
      if (this.remaining[this.remaining.length - 1] === this.last) {
        [this.remaining[0], this.remaining[this.remaining.length - 1]] = [this.remaining[this.remaining.length - 1], this.remaining[0]];
      }
    }
    const message = this.remaining.pop();
    if (!message) throw new Error("Loading message catalogue is empty.");
    this.last = message;
    return message;
  }
}
