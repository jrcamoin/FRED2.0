(() => {
  const tabs = [...document.querySelectorAll('[data-activity]')];
  const chooser = document.getElementById('activity-chooser');
  const back = document.getElementById('activities-back');
  const puzzlePhotos = [...document.querySelectorAll('#puzzle-photos img')];
  const panel = document.getElementById('activity-panel');
  const photos = document.getElementById('familiar-photos');
  const musicPanel = document.getElementById('music-panel');
  const musicPlayer = document.getElementById('music-player');
  const musicStatus = document.getElementById('music-now-playing');
  const musicIntroduce = document.getElementById('music-introduce');
  if (!document.querySelector('.music-track')) {
    musicPlayer.hidden = true;
    musicStatus.hidden = true;
  }
  const title = document.getElementById('activity-title');
  const instructions = document.getElementById('activity-instructions');
  const content = document.getElementById('activity-content');
  const feedback = document.getElementById('activity-feedback');
  const next = document.getElementById('activity-next');
  const lessons = [
    { question: 'Which animal grows from a caterpillar?', choices: ['Butterfly', 'Rabbit', 'Robin'], answer: 'Butterfly', detail: 'A caterpillar becomes a butterfly after spending time in a chrysalis.' },
    { question: 'What helps a seed begin to grow?', choices: ['Water', 'A spoon', 'A bell'], answer: 'Water', detail: 'Seeds need water to begin growing. Many plants also need light and warmth.' },
    { question: 'Which one is a musical instrument?', choices: ['Piano', 'Pillow', 'Plate'], answer: 'Piano', detail: 'A piano makes music when its keys are pressed.' },
    { question: 'What do bees visit in a garden?', choices: ['Flowers', 'Bicycles', 'Shoes'], answer: 'Flowers', detail: 'Bees visit flowers to collect nectar and pollen.' }
  ];
  const pauses = [
    'Look around and find one color you enjoy.',
    'Notice something soft, warm, or comfortable nearby.',
    'Listen for a pleasant sound, near or far.',
    'Think of a song, place, or person that makes you smile.'
  ];
  const phrases = [
    { start: 'A stitch in time saves…', choices: ['nine', 'rain', 'a song'], answer: 'nine' },
    { start: 'Home is where the…', choices: ['heart is', 'river flows', 'sun sets'], answer: 'heart is' },
    { start: 'The early bird catches the…', choices: ['worm', 'train', 'moon'], answer: 'worm' },
    { start: 'Every cloud has a silver…', choices: ['lining', 'button', 'garden'], answer: 'lining' }
  ];
  const photoQuestions = [
    'What do you notice in this picture?',
    'Would you like to tell me about this moment?',
    'Is there a color or detail you enjoy here?'
  ];
  let mode = '';
  let lessonIndex = 0;
  let pauseIndex = 0;
  let phraseIndex = 0;
  let pairCount = 2;
  let puzzleIndex = 0;
  let openCards = [];
  let matched = new Set();
  let locked = false;
  let round = 0;
  let selectedTrackTitle = '';

  function speakPrompt(message) {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(message));
  }

  function shuffle(items) {
    const copy = [...items];
    for (let i = copy.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [copy[i], copy[j]] = [copy[j], copy[i]];
    }
    return copy;
  }

  function pairRound() {
    round++;
    openCards = [];
    matched = new Set();
    locked = false;
    feedback.textContent = '';
    const names = { '🌼': 'flower', '🐦': 'bird', '🍎': 'apple', '☀️': 'sun', '🌳': 'tree', '🐱': 'cat' };
    const symbols = shuffle(Object.keys(names)).slice(0, pairCount);
    const cards = shuffle([...symbols, ...symbols]);
    content.replaceChildren();
    const grid = document.createElement('div');
    grid.className = 'pair-grid';
    grid.setAttribute('aria-label', 'Matching cards');
    cards.forEach((symbol, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'pair-card';
      button.textContent = '?';
      button.setAttribute('aria-label', `Card ${index + 1}, face down`);
      button.addEventListener('click', () => {
        if (locked || matched.has(index) || openCards.includes(index)) return;
        button.textContent = symbol;
        button.setAttribute('aria-label', `Card ${index + 1}, ${names[symbol]}`);
        openCards.push(index);
        if (openCards.length !== 2) return;
        const [first, second] = openCards;
        if (cards[first] === cards[second]) {
          matched.add(first);
          matched.add(second);
          openCards = [];
          feedback.textContent = matched.size === cards.length ? 'All the pairs are together. Nicely done!' : 'These two match!';
        } else {
          locked = true;
          feedback.textContent = 'Take another look. Try any two cards.';
          const thisRound = round;
          window.setTimeout(() => {
            if (thisRound !== round || mode !== 'pairs') return;
            [first, second].forEach(i => {
              grid.children[i].textContent = '?';
              grid.children[i].setAttribute('aria-label', `Card ${i + 1}, face down`);
            });
            openCards = [];
            locked = false;
          }, 1200);
        }
      });
      grid.append(button);
    });
    content.append(grid);
  }

  function addDifficulty() {
    const label = document.createElement('p');
    label.textContent = 'Choose how many pairs feel comfortable:';
    const choices = document.createElement('div');
    choices.className = 'difficulty-choices';
    [2, 3, 4].forEach(count => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = `${count} pairs`;
      button.setAttribute('aria-pressed', String(count === pairCount));
      button.addEventListener('click', () => {
        pairCount = count;
        selectMode('pairs');
      });
      choices.append(button);
    });
    content.prepend(choices);
    content.prepend(label);
  }

  function showPhrase() {
    const phrase = phrases[phraseIndex];
    feedback.textContent = '';
    content.replaceChildren();
    const heading = document.createElement('h3');
    heading.className = 'phrase-heading';
    heading.textContent = phrase.start;
    content.append(heading);
    const choices = document.createElement('div');
    choices.className = 'lesson-choices';
    phrase.choices.forEach(choice => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = choice;
      button.addEventListener('click', () => {
        feedback.textContent = choice === phrase.answer ? `That's the phrase: ${phrase.start} ${phrase.answer}` : `The familiar ending is “${phrase.answer}.”`;
        [...choices.children].forEach(item => item.disabled = true);
      });
      choices.append(button);
    });
    content.append(choices);
  }

  function showPuzzle() {
    content.replaceChildren();
    feedback.textContent = '';
    if (!puzzlePhotos.length) {
      content.textContent = 'A caregiver can add a family photo to make a puzzle.';
      return;
    }
    const image = puzzlePhotos[puzzleIndex % puzzlePhotos.length];
    const intro = document.createElement('p');
    intro.textContent = `Put this familiar picture together. Tap one piece, then tap another to swap them.`;
    content.append(intro);
    const preview = document.createElement('img');
    preview.src = image.src;
    preview.alt = image.alt;
    preview.className = 'puzzle-preview';
    content.append(preview);
    const pieces = shuffle([0, 1, 2, 3]);
    const grid = document.createElement('div');
    grid.className = 'puzzle-grid';
    let selected = -1;
    const render = () => {
      [...grid.children].forEach((tile, index) => {
        tile.style.backgroundImage = `url("${image.src}")`;
        tile.style.backgroundPosition = `${pieces[index] % 2 ? 100 : 0}% ${pieces[index] > 1 ? 100 : 0}%`;
        tile.setAttribute('aria-label', `Picture piece ${pieces[index] + 1} in position ${index + 1}`);
        tile.setAttribute('aria-pressed', String(index === selected));
      });
    };
    for (let i = 0; i < 4; i++) {
      const tile = document.createElement('button');
      tile.type = 'button';
      tile.className = 'puzzle-piece';
      tile.addEventListener('click', () => {
        if (selected < 0) selected = i;
        else {
          [pieces[selected], pieces[i]] = [pieces[i], pieces[selected]];
          selected = -1;
          feedback.textContent = pieces.every((piece, position) => piece === position) ? 'The picture is together. Enjoy looking at it!' : 'The pieces moved. Choose another pair whenever you like.';
        }
        render();
      });
      grid.append(tile);
    }
    render();
    content.append(grid);
  }

  function showColor() {
    content.replaceChildren();
    feedback.textContent = 'Choose a color, then tap a part of the flower.';
    const colors = ['#d94d38', '#e6ac28', '#42815b', '#4777b5', '#a15da4'];
    let selected = colors[0];
    const palette = document.createElement('div');
    palette.className = 'color-palette';
    colors.forEach((color, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.style.backgroundColor = color;
      button.setAttribute('aria-label', `Color ${index + 1}`);
      button.setAttribute('aria-pressed', String(index === 0));
      button.addEventListener('click', () => {
        selected = color;
        [...palette.children].forEach(item => item.setAttribute('aria-pressed', String(item === button)));
      });
      palette.append(button);
    });
    content.append(palette);
    const flower = document.createElement('div');
    flower.className = 'color-flower';
    ['Top petal', 'Left petal', 'Center', 'Right petal', 'Bottom petal'].forEach((part, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `flower-part part-${index}`;
      button.setAttribute('aria-label', part);
      button.addEventListener('click', () => { button.style.backgroundColor = selected; feedback.textContent = `${part} colored. Choose another part or color.`; });
      flower.append(button);
    });
    content.append(flower);
  }

  function showSort() {
    content.replaceChildren();
    feedback.textContent = '';
    const tasks = [
      { item: '🧦 Socks', place: 'Laundry basket', other: 'Kitchen drawer' },
      { item: '🥄 Spoon', place: 'Kitchen drawer', other: 'Laundry basket' },
      { item: '👕 Shirt', place: 'Laundry basket', other: 'Kitchen drawer' }
    ];
    let index = 0;
    const item = document.createElement('h3');
    const choices = document.createElement('div');
    choices.className = 'lesson-choices';
    const render = () => {
      if (index === tasks.length) { item.textContent = 'Thank you for helping FRED sort these things.'; choices.replaceChildren(); return; }
      const task = tasks[index];
      item.textContent = `Where would you put ${task.item}?`;
      choices.replaceChildren();
      shuffle([task.place, task.other]).forEach(place => {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = place;
        button.addEventListener('click', () => {
          feedback.textContent = place === task.place ? 'Thank you. That helps!' : `Let's put it in the ${task.place.toLowerCase()}.`;
          index++;
          render();
        });
        choices.append(button);
      });
    };
    content.append(item, choices);
    render();
  }

  function showLesson() {
    const lesson = lessons[lessonIndex];
    feedback.textContent = '';
    content.replaceChildren();
    const question = document.createElement('h3');
    question.textContent = lesson.question;
    content.append(question);
    const choices = document.createElement('div');
    choices.className = 'lesson-choices';
    lesson.choices.forEach(choice => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = choice;
      button.addEventListener('click', () => {
        feedback.textContent = choice === lesson.answer
          ? `Yes! ${lesson.detail}`
          : `The answer is ${lesson.answer}. ${lesson.detail}`;
        [...choices.children].forEach(item => item.disabled = true);
      });
      choices.append(button);
    });
    content.append(choices);
  }

  function showPause() {
    content.replaceChildren();
    const prompt = document.createElement('p');
    prompt.className = 'quiet-prompt';
    prompt.textContent = pauses[pauseIndex];
    content.append(prompt);
    feedback.textContent = 'You can stay here as long as you like.';
  }

  function selectMode(selected) {
    if (selected !== 'music') musicPlayer.pause();
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    mode = selected;
    round++;
    chooser.hidden = true;
    back.hidden = false;
    photos.hidden = selected !== 'photos';
    musicPanel.hidden = selected !== 'music';
    panel.hidden = selected === 'photos' || selected === 'music';
    if (selected === 'pairs') {
      title.textContent = 'Find a pair';
      instructions.textContent = 'Tap two cards to find pictures that match.';
      next.textContent = 'New round';
      pairRound();
      addDifficulty();
    } else if (selected === 'phrases') {
      title.textContent = 'Finish a phrase';
      instructions.textContent = 'Choose the familiar ending. There is no rush.';
      next.textContent = 'Another phrase';
      showPhrase();
    } else if (selected === 'puzzle') {
      title.textContent = 'Photo puzzle';
      instructions.textContent = 'A picture in four large pieces.';
      next.textContent = 'Another picture';
      showPuzzle();
    } else if (selected === 'color') {
      title.textContent = 'Color a picture';
      instructions.textContent = 'Make the flower any colors you like.';
      next.textContent = 'Start a new flower';
      showColor();
    } else if (selected === 'sort') {
      title.textContent = 'Help FRED sort';
      instructions.textContent = 'Tap where each familiar item belongs.';
      next.textContent = 'Start again';
      showSort();
    } else if (selected === 'learn') {
      title.textContent = 'Explore and learn';
      instructions.textContent = 'Pick an answer to discover a small fact together.';
      next.textContent = 'Another question';
      showLesson();
    } else if (selected === 'pause') {
      title.textContent = 'Quiet moment';
      instructions.textContent = 'A gentle invitation to notice what is around you.';
      next.textContent = 'Another idea';
      showPause();
    }
  }

  tabs.forEach(tab => tab.addEventListener('click', () => selectMode(tab.dataset.activity)));
  back.addEventListener('click', () => {
    musicPlayer.pause();
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    mode = '';
    round++;
    chooser.hidden = false;
    back.hidden = true;
    photos.hidden = true;
    musicPanel.hidden = true;
    panel.hidden = true;
    chooser.querySelector('[data-activity]').focus();
  });
  document.querySelectorAll('.photo-prompt').forEach((button, index) => button.addEventListener('click', () => {
    const question = button.nextElementSibling;
    question.hidden = false;
    question.textContent = photoQuestions[index % photoQuestions.length];
    speakPrompt(question.textContent);
  }));
  document.querySelectorAll('.music-track').forEach(track => track.addEventListener('click', () => {
    musicPlayer.pause();
    musicPlayer.src = track.dataset.src;
    selectedTrackTitle = track.dataset.title;
    musicIntroduce.hidden = !('speechSynthesis' in window);
    musicStatus.textContent = `Now playing: ${track.dataset.title}`;
    document.querySelectorAll('.music-track').forEach(item => item.setAttribute('aria-pressed', String(item === track)));
    musicPlayer.play().catch(() => { musicStatus.textContent = `Ready to play: ${track.dataset.title}. Press play in the player.`; });
  }));
  musicIntroduce.addEventListener('click', () => {
    musicPlayer.pause();
    speakPrompt(`Here is ${selectedTrackTitle}. Would you like to listen together?`);
  });
  next.addEventListener('click', () => {
    if (mode === 'pairs') { pairRound(); addDifficulty(); }
    if (mode === 'phrases') { phraseIndex = (phraseIndex + 1) % phrases.length; showPhrase(); }
    if (mode === 'puzzle') { puzzleIndex++; showPuzzle(); }
    if (mode === 'color') showColor();
    if (mode === 'sort') showSort();
    if (mode === 'learn') { lessonIndex = (lessonIndex + 1) % lessons.length; showLesson(); }
    if (mode === 'pause') { pauseIndex = (pauseIndex + 1) % pauses.length; showPause(); }
  });
})();
