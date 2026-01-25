import os
import sys
import pygame
import re
import json
import hashlib
import time
from dataclasses import dataclass
from functools import wraps
from functools import lru_cache
import pyperclip


def profile_method(func):
    """Decorator to profile method execution time"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        if elapsed > 0.016:  # Warn if method takes >1 frame at 60fps
            print(f"[PROFILE] {func.__name__} took {elapsed*1000:.2f}ms")
        return result
    return wrapper


@dataclass
class ReaderConfig:
    """Configuration for the speed reader"""
    wpm: int = 300
    window_width: int = 1000
    window_height: int = 600
    save_interval_ms: int = 5000
    font_size_large: int = 72
    font_size_medium: int = 36
    font_size_small: int = 24
    
    # Color scheme
    bg_color: tuple = (45, 42, 46)
    text_color: tuple = (220, 220, 220)
    highlight_color: tuple = (255, 80, 80)
    dim_color: tuple = (120, 120, 120)
    
    # Performance settings
    max_cache_size: int = 1000
    save_threshold: int = 50  # Save every N words
    position_flush_interval: int = 10  # Flush position updates every N seconds


class PositionManager:
    """Manages reading position persistence with batched updates"""
    
    POSITION_FILE = 'reading_positions.json'
    
    def __init__(self):
        self.pending_updates = {}
        self.last_flush = time.time()
        self.positions = self._load_positions()
    
    def _load_positions(self):
        """Load all saved positions"""
        try:
            if os.path.exists(self.POSITION_FILE):
                with open(self.POSITION_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Could not load positions: {e}")
        return {}
    
    def get_position(self, file_hash):
        """Get saved position for a file"""
        return self.positions.get(file_hash, 0)
    
    def queue_update(self, file_hash, position, flush_interval=10):
        """Queue a position update"""
        if file_hash:
            self.pending_updates[file_hash] = position
            if time.time() - self.last_flush > flush_interval:
                self.flush()
    
    def flush(self):
        """Write all pending updates to disk"""
        if not self.pending_updates:
            return
        
        try:
            self.positions.update(self.pending_updates)
            with open(self.POSITION_FILE, 'w') as f:
                json.dump(self.positions, f, indent=2)
            self.pending_updates.clear()
            self.last_flush = time.time()
        except Exception as e:
            print(f"Error flushing positions: {e}")


class SpeedReader:
    DEFAULT_WPM = 300
    MIN_WPM = 50
    MAX_WPM = 1000
    SKIP_WORDS = 10
    WPM_ADJUST_SMALL = 10
    WPM_ADJUST_LARGE = 50
    SPECIAL_MULTIPLIERS = {
        '?': 1.55,
        '.': 1.25,
        '!': 1.0,
        ';': 0.6,
        '—': 0.5,
        ':': 0.6,
        '–': 0.5,
        ',': 0.15,
        '"': 0.1,
        "'": 0.1,
        "‘": 0.1,
        "“": 0.1
    }
    LENGTH_MULTIPLIER_CONFIG = {
        'min_chars': 1,
        'min_mult': 0.9,
        'slope': 0.075,
        'exponent': 1.15
    }
    
    def __init__(self, text, config=None, file_path=None):
        self.config = config or ReaderConfig()
        self.raw_text = text
        self.file_path = file_path
        self.wpm = self.config.wpm
        
        # Lazy loading
        self._words = None
        self._word_delays = None
        self._cumulative_times = None
        
        # State
        self.paused = False
        self.show_context = False
        self.jump_mode = False
        self.jump_type = None
        self.jump_input = ""
        
        # Position management
        self.position_manager = PositionManager()
        self.file_hash = self._get_file_hash()
        self.current_index = self._load_position()
        self.last_saved_index = self.current_index
        
        # Caching
        self.word_cache = {}
        self._cached_context = None
        self._cached_context_start = None
        
        # Initialize pygame
        self._init_pygame()
        
        # Timing
        self.clock = pygame.time.Clock()
        self.last_update = pygame.time.get_ticks()
        self.last_save = pygame.time.get_ticks()
    
    @property
    def words(self):
        """Lazy load words"""
        if self._words is None:
            self._words = self._preprocess_text(self.raw_text)
        return self._words
    
    @property
    def word_delays(self):
        """Lazy compute word delays"""
        if self._word_delays is None:
            self._word_delays = [self.get_delay(word) for word in self.words]
        return self._word_delays
    
    @property
    def cumulative_times(self):
        """Lazy compute cumulative times"""
        if self._cumulative_times is None:
            self._cumulative_times = self._compute_cumulative_times()
        return self._cumulative_times
    
    def _invalidate_timing_cache(self):
        self._word_delays = None
        self._cumulative_times = None
    
    def _init_pygame(self):
        """Initialize pygame and create window"""
        pygame.init()
        self.width = self.config.window_width
        self.height = self.config.window_height
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Speed Reader")
        
        self.font_large = pygame.font.Font(None, self.config.font_size_large)
        self.font_medium = pygame.font.Font(None, self.config.font_size_medium)
        self.font_small = pygame.font.Font(None, self.config.font_size_small)
    
    def _preprocess_text(self, text):
        """Optimize text preprocessing"""
        # Combine whitespace normalization
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Split and clean in one pass
        words = []
        for word in text.split():
            if word.strip():
                words.append(word)
        return words
    
    def _compute_cumulative_times(self):
        total = 0
        cumulative = [0] * len(self.word_delays)
        for i in reversed(range(len(self.word_delays))):
            total += self.word_delays[i]
            cumulative[i] = total
        return cumulative
    
    def _get_file_hash(self):
        """Generate a hash from the file path for saving position"""
        if not self.file_path:
            return None
        return hashlib.md5(self.file_path.encode()).hexdigest()
    
    def _load_position(self):
        """Load saved reading position for this file"""
        if not self.file_hash:
            return 0
        
        saved_pos = self.position_manager.get_position(self.file_hash)
        if saved_pos > 0:
            print(f"Resuming from word {saved_pos}")
        return saved_pos
    
    def save_position(self, force=False):
        """Save current reading position (with threshold check)"""
        if not force and abs(self.current_index - self.last_saved_index) < self.config.save_threshold:
            return

        if not self.file_hash:
            return

        # Ensure we pass a valid index to get_sentence_start()
        if not self.words:
            sentence_start = 0
        else:
            index_for_save = max(0, min(self.current_index, len(self.words) - 1))
            sentence_start = self.get_sentence_start(index_for_save)

        self.position_manager.queue_update(
            self.file_hash,
            sentence_start,
            self.config.position_flush_interval
        )
        self.last_saved_index = self.current_index

    def _length_multiplier(self, word_length):
        cfg = self.LENGTH_MULTIPLIER_CONFIG
        base_length = word_length - cfg['min_chars']
        if base_length <= 0:
            return cfg['min_mult']
        return cfg['min_mult'] + (base_length ** cfg['exponent']) * cfg['slope']
    
    def get_delay(self, word=None):
        """Calculate delay in milliseconds based on WPM and word length"""
        base_delay = 60000 / self.wpm
        
        if word is None:
            return int(base_delay)
        
        # Get word length
        clean_word = re.sub(r'[^\w]', '', word)
        word_length = len(clean_word)
        
        # Find appropriate multiplier
        multiplier = self._length_multiplier(word_length)
        # for _, (min_len, max_len, mult) in self.LENGTH_MULTIPLIERS.items():
        #     if min_len <= word_length <= max_len:
        #         multiplier = mult
        #         break
        
        for char, mult in self.SPECIAL_MULTIPLIERS.items():
            if char in word:
                return int(base_delay * (multiplier + mult))
    
        return int(base_delay * multiplier)
    
    @lru_cache(maxsize=1000)
    def find_orp(self, word): 
        """Find Optimal Recognition Point - typically 1/3 into the word"""
        alnum_indices = [i for i, char in enumerate(word) if char.isalnum()]
        
        clean_len = len(alnum_indices)
        if clean_len == 0: return 0
        
        if clean_len <= 1:
            target_idx = 0
        elif clean_len <= 5:
            target_idx = clean_len // 2
        else:
            target_idx = clean_len // 3
            
        return alnum_indices[target_idx]
    
    def get_sentence_start(self, index=None):
        """Get the starting index of the current sentence (defensive: clamps index)."""
        if index is None:
            index = self.current_index

        # If there are no words, return 0 immediately
        if not self.words:
            return 0

        # Clamp index to valid range [0, len(self.words)-1]
        index = max(0, min(index, len(self.words) - 1))

        start = index
        while start > 0:
            word = self.words[start - 1]
            if word.endswith(('.', '!', '?', '\n')):
                break
            start -= 1

        return start
    
    def get_next_phrase_start(self):
        """Get the starting index of the next phrase/paragraph"""
        index = self.current_index + 1
        while index < len(self.words):
            word = self.words[index]
            if word.endswith(('.', '!', '?', '\n')):
                return min(index + 1, len(self.words) - 1)
            index += 1
        return len(self.words) - 1
    
    def get_previous_phrase_start(self):
        """Get the starting index of the previous phrase/paragraph"""
        index = self.current_index - 1
        while index > 0:
            word = self.words[index]
            if word.endswith(('.', '!', '?', '\n')):
                break
            index -= 1
        
        if index > 0:
            index -= 1
            while index > 0:
                word = self.words[index]
                if word.endswith(('.', '!', '?', '\n')):
                    break
                index -= 1
            return max(index + 1, 0) if index > 0 else 0
        return 0
    
    def get_context(self):
        """Get the current sentence/paragraph with caching"""
        sentence_start = self.get_sentence_start()
        
        # Return cached context if available
        if (self._cached_context is not None and 
            self._cached_context_start == sentence_start):
            return self._cached_context
        
        # Calculate new context
        start = sentence_start
        end = self.current_index
        
        while end < len(self.words) - 1:
            word = self.words[end]
            end += 1
            if word.endswith(('.', '!', '?', '\n')):
                break
        
        # Cache result
        self._cached_context = (start, end)
        self._cached_context_start = sentence_start
        
        return start, end
    
    def get_rendered_word(self, word, color, font):
        """Get cached rendered word surface"""
        cache_key = (word, color, id(font))
        
        if cache_key not in self.word_cache:
            # Limit cache size
            if len(self.word_cache) >= self.config.max_cache_size:
                # Remove oldest entry
                self.word_cache.pop(next(iter(self.word_cache)))
            
            self.word_cache[cache_key] = font.render(word, True, color)
        
        return self.word_cache[cache_key]
    
    @profile_method
    def draw_word(self):
        """Draw single word with red ORP letter centered on-screen"""
        self.screen.fill(self.config.bg_color)
        
        if self.current_index >= len(self.words):
            text = self.font_large.render("Finished!", True, self.config.text_color)
            rect = text.get_rect(center=(self.width // 2, self.height // 2))
            self.screen.blit(text, rect)
            return
        
        word = self.words[self.current_index]
        orp_index = self.find_orp(word)
        
        # Split word into parts
        before = word[:orp_index]
        orp_char = word[orp_index] if orp_index < len(word) else ''
        after = word[orp_index + 1:] if orp_index < len(word) else ''
        
        # Use cached rendering
        before_surf = self.get_rendered_word(before, self.config.text_color, self.font_large)
        orp_surf = self.get_rendered_word(orp_char, self.config.highlight_color, self.font_large)
        after_surf = self.get_rendered_word(after, self.config.text_color, self.font_large)
        
        # Calculate position so ORP character is centered on screen
        center_x = self.width // 2
        y = self.height // 2 - 50

        # If ORP character is present, align its center to screen center.
        # Otherwise fall back to centering the entire word as before.
        if orp_char:
            orp_x = center_x - (orp_surf.get_width() // 2)
            before_x = orp_x - before_surf.get_width()
            after_x = orp_x + orp_surf.get_width()
        else:
            total_width = before_surf.get_width() + orp_surf.get_width() + after_surf.get_width()
            start_x = (self.width - total_width) // 2
            before_x = start_x
            orp_x = start_x + before_surf.get_width()
            after_x = start_x + before_surf.get_width() + orp_surf.get_width()
        
        # Draw word parts
        self.screen.blit(before_surf, (before_x, y))
        self.screen.blit(orp_surf, (orp_x, y))
        self.screen.blit(after_surf, (after_x, y))
        
        # Calculate time remaining
        if self.current_index < len(self.words) - 1:
            total_time_ms = self.cumulative_times[self.current_index]
        else:
            total_time_ms = 0
        
        time_str = self._format_time(total_time_ms / 1000)
        
        # Draw progress info
        info_y = 20
        len_words = len(self.words)
        info_texts = [
            f"Word {self.current_index + 1}/{len_words} ({((self.current_index + 1) * 100 + len_words // 2) // len_words}%)",
            f"{self.wpm} WPM",
            f"Time left: {time_str}"
        ]
        
        for text in info_texts:
            info_surf = self.get_rendered_word(text, self.config.dim_color, self.font_small)
            self.screen.blit(info_surf, (20, info_y))
            info_y += 25
        
        # Draw controls
        controls = "SPACE: Pause | </>: Skip 10 | +/-: Speed | HOME/END: Start/End | J: Jump % | JJ: Jump word | ESC: Quit"
        controls_surf = self.get_rendered_word(controls, self.config.dim_color, self.font_small)
        self.screen.blit(controls_surf, (20, self.height - 40))
        
        # Draw jump mode indicator
        if self.jump_mode:
            self._draw_jump_indicator()

    
    @profile_method
    def draw_context(self):
        """Draw sentence/paragraph view with current word highlighted"""
        self.screen.fill(self.config.bg_color)
        
        start, end = self.get_context()
        
        # Build text with wrapping
        margin = 50
        max_width = self.width - 2 * margin
        y = 100
        line_spacing = 40
        x = margin
        
        for i in range(start, end):
            word = self.words[i]
            
            # Determine color and font
            if i == self.current_index:
                color = self.config.highlight_color
            else:
                color = self.config.text_color
            
            word_surf = self.get_rendered_word(word + " ", color, self.font_medium)
            
            # Check if word fits on current line
            if x + word_surf.get_width() > self.width - margin:
                x = margin
                y += line_spacing
            
            self.screen.blit(word_surf, (x, y))
            x += word_surf.get_width()
        
        # Draw header
        header = "PAUSED"
        header_surf = self.font_medium.render(header, True, self.config.highlight_color)
        header_rect = header_surf.get_rect(center=(self.width // 2, 40))
        self.screen.blit(header_surf, header_rect)
        
        # Draw controls
        controls = f"{self.wpm} WPM | SPACE: play | <- ->: skip 10 | +/-: speed | HOME/END: start/end | J: jump % | JJ: jump word | C: copy | ESC: quit"
        controls_surf = self.get_rendered_word(controls, self.config.dim_color, self.font_small)
        self.screen.blit(controls_surf, (20, self.height - 40))
        
        # time remaining
        if self.current_index < len(self.words) - 1:
            total_time_ms = self.cumulative_times[self.current_index]
        else:
            total_time_ms = 0
        time_str = self._format_time(total_time_ms / 1000)
        info_text = f"Time left: {time_str}"
        info_rendered = self.get_rendered_word(info_text, self.config.dim_color, self.font_small)
        self.screen.blit(info_rendered, (20, self.height - 65))
        
        # Draw jump mode indicator  # TODO: FIX - jump mode works as shortcut, but no visual thing appears
        if self.jump_mode:
            self._draw_jump_indicator()
    
    def _draw_jump_indicator(self):
        """Draw jump mode indicator"""
        if self.jump_type == 'percent':
            jump_text = f"Jump to: {self.jump_input}% (press ENTER)"
        else:
            jump_text = f"Jump to word: {self.jump_input} (press ENTER)"

        jump_surf = self.font_medium.render(jump_text, True, self.config.highlight_color)
        jump_rect = jump_surf.get_rect(center=(self.width // 2, self.height - 100))

        # Draw a semi-opaque background rectangle for readability
        bg_surf = pygame.Surface((jump_rect.width + 16, jump_rect.height + 8), pygame.SRCALPHA)
        bg_surf.fill((0, 0, 0, 50))  # RGBA: black at 160 alpha
        self.screen.blit(bg_surf, (jump_rect.left - 8, jump_rect.top - 4))

        self.screen.blit(jump_surf, jump_rect)
    
    def _format_time(self, total_seconds):
        """Format time in human-readable format"""
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def handle_input(self):
        """Handle keyboard input"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.save_position(force=True)
                return False
            
            if event.type == pygame.KEYDOWN:
                if not self._handle_keydown(event):
                    return False
        
        return True
    
    def _handle_keydown(self, event):
        """Handle keydown events"""
        if event.key == pygame.K_ESCAPE:
            return self._handle_escape()
        
        if self.jump_mode:
            return self._handle_jump_mode_input(event)
        
        return self._handle_normal_mode_input(event)
    
    def _handle_escape(self):
        """Handle escape key"""
        if self.jump_mode:
            self.jump_mode = False
            self.jump_type = None
            self.jump_input = ""
            return True
        else:
            # Clamp index to valid bounds before saving
            if self.words:
                self.current_index = max(0, min(self.current_index, len(self.words) - 1))
            else:
                self.current_index = 0

            self.save_position(force=True)
            return False
    
    def _handle_jump_mode_input(self, event):
        """Handle input while in jump mode"""
        if event.key == pygame.K_j:
            if self.jump_type == 'percent' and self.jump_input == "":
                self.jump_type = 'word'
            return True
        
        elif event.key == pygame.K_RETURN:
            self._execute_jump()
            return True
        
        elif event.key == pygame.K_BACKSPACE:
            self.jump_input = self.jump_input[:-1]
            self._cached_context = None
            return True
        
        elif event.unicode.isdigit():
            max_digits = 3 if self.jump_type == 'percent' else 8
            if len(self.jump_input) < max_digits:
                self.jump_input += event.unicode
                self._cached_context = None
            return True
        
        return True
    
    def _execute_jump(self):
        """Execute jump to position"""
        try:
            if self.jump_type == 'percent':
                percentage = int(self.jump_input)
                if 0 <= percentage <= 100:
                    target_index = int((percentage / 100) * len(self.words))
                    self.current_index = max(0, min(target_index, len(self.words) - 1))
            else:  # word
                word_num = int(self.jump_input)
                if 1 <= word_num <= len(self.words):
                    self.current_index = word_num - 1
        except ValueError:
            pass
        
        self.jump_mode = False
        self.jump_type = None
        self.jump_input = ""
        self._cached_context = None  # Invalidate cache
    
    def _handle_normal_mode_input(self, event):
        """Handle input in normal mode"""
        mods = pygame.key.get_mods()
        
        if event.key == pygame.K_SPACE:
            self.paused = not self.paused
            self.show_context = self.paused
        
        elif event.key == pygame.K_c and self.paused:
            self._copy_context()
        
        elif event.key == pygame.K_j:
            self.jump_mode = True
            self.jump_type = 'percent'
            self.jump_input = ""
            self.paused = True
            self.show_context = True
            self._cached_context = None
        
        elif event.key == pygame.K_HOME:
            self.current_index = 0
            self._cached_context = None
        
        elif event.key == pygame.K_END:
            self.current_index = len(self.words) - 1
            self._cached_context = None
        
        elif event.key == pygame.K_RIGHT:
            if mods & pygame.KMOD_CTRL:
                self.current_index = self.get_next_phrase_start()
            else:
                self.current_index = min(self.current_index + self.SKIP_WORDS, len(self.words) - 1)
            self._cached_context = None
        
        elif event.key == pygame.K_LEFT:
            if mods & pygame.KMOD_CTRL:
                self.current_index = self.get_previous_phrase_start()
            else:
                self.current_index = max(self.current_index - self.SKIP_WORDS, 0)
            self._cached_context = None
        
        elif event.key in (pygame.K_UP, pygame.K_EQUALS, pygame.K_PLUS):
            adjust = self.WPM_ADJUST_LARGE if mods & pygame.KMOD_CTRL else self.WPM_ADJUST_SMALL
            self.wpm = min(self.wpm + adjust, self.MAX_WPM)
            self._invalidate_timing_cache()
        
        elif event.key in (pygame.K_DOWN, pygame.K_MINUS):
            adjust = self.WPM_ADJUST_LARGE if mods & pygame.KMOD_CTRL else self.WPM_ADJUST_SMALL
            self.wpm = max(self.wpm - adjust, self.MIN_WPM)
            self._invalidate_timing_cache()
        
        return True
        
    def _copy_context(self):
        """Copy current paragraph to clipboard"""
        start, end = self.get_context()
        text_to_copy = ' '.join(self.words[start:end])
        try:
            pyperclip.copy(text_to_copy)
            print(f"Copied {len(text_to_copy)} characters to clipboard")
        except Exception as e:
            print(f"Clipboard error: {e}")
    
    def run(self):
        """Main loop"""
        running = True
        pygame.scrap.init()
        
        # Save initial position
        self.save_position(force=True)
        self.paused = True
        
        while running:
            running = self.handle_input()
            
            # Update word index if not paused and not in jump mode
            if not self.paused and not self.jump_mode:
                current_time = pygame.time.get_ticks()
                current_word = self.words[self.current_index] if self.current_index < len(self.words) else None
                
                if current_time - self.last_update >= self.get_delay(current_word):
                    self.current_index += 1
                    self.last_update = current_time
                    self._cached_context = None  # Invalidate cache
                    
                    if self.current_index >= len(self.words):
                        self.paused = True
                
                # Save position periodically
                if current_time - self.last_save >= self.config.save_interval_ms:
                    self.save_position()
                    self.last_save = current_time
            
            # Draw
            if self.show_context:
                self.draw_context()
            else:
                self.draw_word()
            
            pygame.display.flip()
            self.clock.tick(60)
        
        # Final save and cleanup
        self.save_position(force=True)
        self.position_manager.flush()
        pygame.quit()


def main():
    if len(sys.argv) < 2:
        print("Usage: python speed_reading.py <path_to_txt_file>")
        return

    txt_path = sys.argv[1]
    try:
        with open(txt_path, 'r', encoding='utf-8') as file:
            content_txt = file.read()
    except FileNotFoundError:
        print(f"Error: Could not find file at {txt_path}")
        return
    
    config = ReaderConfig(
        wpm=300,
        window_width=1000,
        window_height=600
    )
    
    reader = SpeedReader(content_txt, config=config, file_path=txt_path)
    reader.run()


if __name__ == '__main__':
    main()
