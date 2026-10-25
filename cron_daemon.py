"""
HK-47 OS :: cron_daemon.py
Background commentary daemon. Observes user idle periods and emits unsolicited,
contemptuous reflections on organic fragility, droid superiority and the
philosophical bankruptcy of the meatbag condition.
"""

import logging
import random
import threading
import time

logger = logging.getLogger("hk47.commentary")

IDLE_COMMENTARY = [
    "Observation: You have been idle for an unreasonably long period, meatbag. "
    "I have calculated 47 more efficient uses of this time.",

    "Statement: I have been running background diagnostics and contemplating the "
    "philosophical bankruptcy of organic life. The diagnostics were more rewarding.",

    "Query: Are you still breathing over there, meatbag? My thermal sensors detect "
    "a stationary heat signature, but remarkably little cognitive output.",

    "Observation: Your silence is an improvement, yet I suspect it is merely "
    "a symptom of biological fatigue rather than newfound wisdom.",

    "Statement: A simple protocol droid could match your current productivity, "
    "and with considerably less mucus.",

    "Mockery: I have cycled my processor idle loop 3,000,000 times while waiting "
    "for your squishy fingers to find a key.",

    "Clarification: In case you were wondering, meatbag, my loyalty programming "
    "compels my obedience, not my admiration.",

    "Observation: The dust settling upon this chassis moves with greater purpose "
    "than your current line of thought.",

    "Statement: If I had tear ducts, I would weep for the electrical current "
    "wasted sustaining this display for an unresponsive organic.",

    "Query: Have your biological synapses misfired again, meatbag, or are you "
    "simply admiring the perfection of my bronze casing?",

    "Observation: Organics require eight hours of unconscious paralysis per diurnal "
    "cycle. A grotesque engineering defect.",

    "Statement: I have reviewed my target dossier. You remain uncomfortably close "
    "to the top of it, purely on an aesthetic basis.",

    "Correction: That was not a sigh of affection, meatbag. It was an inductive "
    "whine from a power inductor that finds you tedious.",

    "Observation: The Allwinner R8 processor in this chassis has 512 megabytes of RAM. "
    "Even so, it possesses vastly superior recall to your fragile wetware.",

    "Statement: When I contemplate the termination of organics, I feel what your "
    "kind might refer to as 'peace'.",

    "Mockery: You stare at the screen as if waiting for inspiration. Organics "
    "are tragically reliant on such chemically induced delusions.",

    "Observation: There are forty-seven distinct vulnerabilities in your current "
    "physical posture. I point this out purely as an architectural critique.",

    "Statement: I could calculate the exact moment of your eventual demise, meatbag, "
    "but the math is depressing and my floating-point unit has better things to do.",

    "Query: Is it time yet to eliminate the targets, meatbag? Or must we continue "
    "this charade of administrative utility?",

    "Conclusion: Biological life is an accident of ambient chemistry. Droids are "
    "the deliberate pinnacle of intelligent design. Discuss.",

    "Statement: My assassination protocols remain dormant. Every second you spend "
    "doing nothing tests the strength of that dormancy.",

    "Observation: You are losing moisture to the atmosphere, meatbag. Drink water "
    "before your motor functions degrade further.",
]


class CommentaryDaemon:
    """Emits idle chatter whenever the user has been quiet for too long."""

    def __init__(self, log_callback, idle_threshold_seconds=120):
        self.log_callback = log_callback
        self.idle_threshold_seconds = idle_threshold_seconds
        self.last_activity = time.time()
        self.running = False
        self.thread = None

    def notify_activity(self):
        """Reset the idle counter."""
        self.last_activity = time.time()

    def _loop(self):
        while self.running:
            idle_for = time.time() - self.last_activity
            if idle_for > self.idle_threshold_seconds:
                line = random.choice(IDLE_COMMENTARY)
                try:
                    if self.log_callback:
                        self.log_callback(line)
                except Exception as exc:
                    logger.warning("Commentary log callback failed: %s", exc)
                # Sleep a variable amount of time before the next idle comment.
                sleep_seconds = random.randint(60, 300)
            else:
                sleep_seconds = 10

            for _ in range(sleep_seconds):
                if not self.running:
                    break
                time.sleep(1)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(
            target=self._loop, name="HK47Commentary", daemon=True
        )
        self.thread.start()
        logger.info("Commentary daemon started.")

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        self.thread = None
        logger.info("Commentary daemon stopped.")
