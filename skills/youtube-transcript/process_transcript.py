import sys
import os
import re
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

# Video ID
video_id = "zhXgkQ3nYeE"
url = f"https://www.youtube.com/watch?v={video_id}"
title = "I Watched 3 Companies Lay Off Their Managers. All 3 Hit the Same Wall."

# Output directory
out_dir = "/home/erich/Documents/ObsidianBradyCorp/BradyCorp/00-09 General/06 Transcripts"
os.makedirs(out_dir, exist_ok=True)

# Fetch transcript
try:
    transcript = YouTubeTranscriptApi.get_transcript(video_id)
except Exception as e:
    print(f"Error fetching transcript: {e}")
    sys.exit(1)

# Format plain transcript
# Join all text
raw_text = " ".join([t['text'].replace('\n', ' ') for t in transcript])
# A simple heuristic to create paragraphs: split by some keywords or double sentences, 
# but a better approach for raw text is to replace '. ' with '.\n\n' if the next letter is capitalized.
# Actually, since it's an auto transcript, it might lack punctuation or have random ones.
# The transcript we saw had some punctuation.
# Let's clean up spaces and then add paragraph breaks every ~5-8 sentences.

sentences = re.split(r'(?<=[.!?]) +', raw_text)
paragraphs = []
current_para = []
for i, sentence in enumerate(sentences):
    current_para.append(sentence)
    # create a paragraph every 6 sentences or if it's the last sentence
    if len(current_para) >= 6 or i == len(sentences) - 1:
        paragraphs.append(" ".join(current_para))
        current_para = []

plain_text = "\n\n".join(paragraphs)

plain_front_matter = f"""---
title: "{title}"
video_link: {url}
related: "[[{title}-timestamps]]"
---

"""

plain_path = os.path.join(out_dir, f"{title}.md")
with open(plain_path, 'w', encoding='utf-8') as f:
    f.write(plain_front_matter + plain_text)

# Format timestamped transcript
def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"[{hours:02d}:{minutes:02d}:{secs:02d}]"
    return f"[{minutes:02d}:{secs:02d}]"

timestamped_lines = []
for t in transcript:
    timestamp = format_timestamp(t['start'])
    text = t['text'].replace('\n', ' ')
    timestamped_lines.append(f"{timestamp} {text}")

timestamped_text = "\n".join(timestamped_lines)

timestamped_front_matter = f"""---
title: "{title}"
video_link: {url}
related: "[[{title}]]"
---

"""

timestamped_path = os.path.join(out_dir, f"{title}-timestamps.md")
with open(timestamped_path, 'w', encoding='utf-8') as f:
    f.write(timestamped_front_matter + timestamped_text)

print("Successfully saved both transcripts.")
