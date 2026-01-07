import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  Timer, CheckCircle2, ListTodo, Flame, Play, Pause, 
  RotateCcw, Plus, Trash2, Award, X, ExternalLink, 
  BrainCircuit, Zap, Sparkles, Settings, Home, 
  Moon, Sun, Volume2, Info, ShieldCheck, Mail, Crown, ShoppingBag, ChevronRight,
  BookOpen, Music, Wind, Coffee, CloudRain, Star, Newspaper, ArrowLeft, Bell
} from 'lucide-react';
import { initializeApp } from 'firebase/app';
import { 
  getFirestore, collection, doc, onSnapshot, 
  addDoc, updateDoc, deleteDoc, setDoc, query 
} from 'firebase/firestore';
import { getAuth, signInAnonymously, onAuthStateChanged, signInWithCustomToken } from 'firebase/auth';

// --- Firebase Initialization ---
const firebaseConfig = JSON.parse(__firebase_config);
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
const appId = typeof __app_id !== 'undefined' ? __app_id : 'focusbuddy-global-v1';

// --- AdSense Component ---
const AdSenseUnit = ({ slot, darkMode }) => {
  useEffect(() => {
    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    } catch (e) {}
  }, []);

  return (
    <div className={`mx-4 my-4 p-4 rounded-3xl border-2 border-dashed transition-all overflow-hidden text-center ${
      darkMode ? 'bg-slate-800 border-slate-700' : 'bg-slate-100 border-slate-200 shadow-inner'
    }`}>
      <span className="text-[10px] font-black uppercase text-slate-400 mb-2 block tracking-widest text-center w-full">Sponsored Ad</span>
      <div className="flex items-center justify-center min-h-[100px] text-slate-400 italic text-xs">
        <ins className="adsbygoogle"
             style={{ display: 'block' }}
             data-ad-client="ca-pub-0000000000000000" 
             data-ad-slot={slot}
             data-ad-format="auto"
             data-full-width-responsive="true"></ins>
        AdSense Integration Slot
      </div>
    </div>
  );
};

const App = () => {
  // --- State Management ---
  const [user, setUser] = useState(null);
  const [activeTab, setActiveTab] = useState('home');
  const [selectedPost, setSelectedPost] = useState(null);
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('fb-dark-mode');
    return saved ? JSON.parse(saved) : false;
  });
  
  const [tasks, setTasks] = useState([]);
  const [brainDump, setBrainDump] = useState([]);
  const [stats, setStats] = useState({ points: 0, streak: 0, sessions: 0 });
  
  const [dumpInput, setDumpInput] = useState('');
  const [newTask, setNewTask] = useState('');
  const [taskEnergy, setTaskEnergy] = useState('medium');
  
  const [timeLeft, setTimeLeft] = useState(25 * 60);
  const [isActive, setIsActive] = useState(false);
  const [isBreak, setIsBreak] = useState(false);
  
  const [notification, setNotification] = useState(null);
  const [currentMusic, setCurrentMusic] = useState(null);
  const audioRef = useRef(null);

  // --- ADHD Music Tracks ---
  const musicTracks = [
    { id: 'brown', name: 'Brown Noise', icon: <Wind size={18} />, desc: 'Deep focus', url: 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3' },
    { id: 'lofi', name: 'Lofi Beats', icon: <Coffee size={18} />, desc: 'Chill beats', url: 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3' },
    { id: 'binaural', name: 'Binaural', icon: <Sparkles size={18} />, desc: 'Gamma waves', url: 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3' },
    { id: 'rain', name: 'Ambient Rain', icon: <CloudRain size={18} />, desc: 'Cozy focus', url: 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3' },
  ];

  // --- Blog Content (SEO Power) ---
  const blogPosts = [
    { 
      id: 1, 
      title: "How Binaural Beats Help ADHD Brains", 
      excerpt: "Discover the science behind sound frequencies and focus...", 
      content: "Binaural beats involve playing two slightly different frequencies in each ear. For ADHD, 40Hz (Gamma) is often cited as a tool for increasing concentration. By 'entraining' the brain to these frequencies, users report lower distractibility and higher task completion rates.",
      author: "Dr. Focus",
      date: "Jan 8, 2026"
    },
    { 
      id: 2, 
      title: "The Magic of 'Body Doubling'", 
      excerpt: "Why working with others makes you more productive...", 
      content: "Body doubling is a productivity strategy used by folks with ADHD to get things done. It involves working alongside another person. The other person doesn't even need to help you; their presence acts as a 'social anchor' that keeps your brain on task.",
      author: "Alex Rivers",
      date: "Jan 7, 2026"
    },
    { 
      id: 3, 
      title: "Stop Fighting Your Time Blindness", 
      excerpt: "Practical tips to manage your perception of time...", 
      content: "Time blindness is the inability to sense the passing of time. Using visual timers (like the one in FocusBuddy) turns time into a physical resource you can see depleting, which reduces the anxiety of 'where did the hour go?'",
      author: "Morgan J.",
      date: "Jan 5, 2026"
    }
  ];

  // --- Rank Logic ---
  const getRank = (pts) => {
    if (pts >= 1000) return "Master";
    if (pts >= 500) return "Expert";
    if (pts >= 100) return "Focused";
    return "Novice";
  };

  // --- Theme & SEO Effect ---
  useEffect(() => {
    localStorage.setItem('fb-dark-mode', JSON.stringify(darkMode));
    if (darkMode) document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
    
    const titles = {
      home: 'Dashboard | FocusBuddy',
      focus: 'Deep Focus Mode | FocusBuddy',
      missions: 'My Missions | FocusBuddy',
      blog: 'ADHD Insights & Blog | FocusBuddy',
      settings: 'Management | FocusBuddy'
    };
    document.title = titles[activeTab] || 'FocusBuddy - ADHD Companion';

    // Analytics Placeholder
    console.log(`Analytics: Page view tracked for ${activeTab}`);
  }, [darkMode, activeTab]);

  // --- Audio Engine ---
  useEffect(() => {
    if (currentMusic) {
      const track = musicTracks.find(t => t.id === currentMusic);
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      audioRef.current = new Audio(track.url);
      audioRef.current.loop = true;
      audioRef.current.play().catch(err => {
        console.warn("Autoplay blocked. User needs to interact first.", err);
      });
    } else {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    }
    return () => {
      if (audioRef.current) audioRef.current.pause();
    };
  }, [currentMusic]);

  // --- Auth Flow ---
  useEffect(() => {
    const initAuth = async () => {
      try {
        if (typeof __initial_auth_token !== 'undefined' && __initial_auth_token) {
          await signInWithCustomToken(auth, __initial_auth_token);
        } else {
          await signInAnonymously(auth);
        }
      } catch (error) {}
    };
    initAuth();
    const unsubscribe = onAuthStateChanged(auth, setUser);
    return () => unsubscribe();
  }, []);

  // --- Real-time Sync ---
  useEffect(() => {
    if (!user) return;
    const unsubTasks = onSnapshot(collection(db, 'artifacts', appId, 'users', user.uid, 'tasks'), s => setTasks(s.docs.map(d => ({ id: d.id, ...d.data() }))));
    const unsubDump = onSnapshot(collection(db, 'artifacts', appId, 'users', user.uid, 'braindump'), s => setBrainDump(s.docs.map(d => ({ id: d.id, ...d.data() }))));
    const unsubStats = onSnapshot(doc(db, 'artifacts', appId, 'users', user.uid, 'stats', 'overall'), d => {
      if (d.exists()) setStats(d.data());
      else setDoc(doc(db, 'artifacts', appId, 'users', user.uid, 'stats', 'overall'), { points: 0, streak: 1, sessions: 0 });
    });
    return () => { unsubTasks(); unsubDump(); unsubStats(); };
  }, [user]);

  // --- Timer Engine ---
  useEffect(() => {
    let interval = null;
    if (isActive && timeLeft > 0) interval = setInterval(() => setTimeLeft(p => p - 1), 1000);
    else if (timeLeft === 0) {
      setIsActive(false);
      completeSession();
    }
    return () => clearInterval(interval);
  }, [isActive, timeLeft]);

  const completeSession = async () => {
    if (!user) return;
    const newPoints = (Number(stats.points) || 0) + (isBreak ? 5 : 30);
    await updateDoc(doc(db, 'artifacts', appId, 'users', user.uid, 'stats', 'overall'), { 
      points: newPoints, 
      sessions: (stats.sessions || 0) + (isBreak ? 0 : 1) 
    });
    setNotification(isBreak ? "Break over! Ready for a new mission?" : "Success! Session completed. Take a break!");
    setIsBreak(!isBreak);
    setTimeLeft(isBreak ? 25 * 60 : 5 * 60);
  };

  const handleAddTask = async (e) => {
    e.preventDefault();
    if (!newTask.trim() || !user) return;
    await addDoc(collection(db, 'artifacts', appId, 'users', user.uid, 'tasks'), { text: newTask, completed: false, energy: taskEnergy, createdAt: Date.now() });
    setNewTask('');
  };

  // --- UI Views ---

  const HomeView = () => (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 text-left">
      <div className={`p-8 rounded-[40px] ${darkMode ? 'bg-indigo-900/40 border-indigo-800' : 'bg-indigo-600 border-transparent'} border-2 text-white shadow-2xl relative overflow-hidden`}>
        <div className="relative z-10 text-left">
          <h2 className="text-3xl font-black mb-2 tracking-tight">Mission Control 🛰️</h2>
          <p className="text-indigo-100 text-sm mb-6 font-medium">Small wins lead to major breakthroughs.</p>
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-white/10 p-4 rounded-2xl backdrop-blur-md border border-white/10 text-center">
              <span className="block text-[8px] font-black uppercase opacity-60 tracking-widest mb-1">XP Points</span>
              <span className="text-xl font-black block tabular-nums">{stats.points}</span>
            </div>
            <div className="bg-white/10 p-4 rounded-2xl backdrop-blur-md border border-white/10 text-center">
              <span className="block text-[8px] font-black uppercase opacity-60 tracking-widest mb-1">Sessions</span>
              <span className="text-xl font-black block tabular-nums">{stats.sessions}</span>
            </div>
            <div className="bg-white/10 p-4 rounded-2xl backdrop-blur-md border border-white/10 text-center flex flex-col justify-center">
              <span className="block text-[8px] font-black uppercase opacity-60 tracking-widest mb-1">Rank</span>
              <span className="text-[10px] font-black uppercase block tracking-tighter text-amber-300">{getRank(stats.points)}</span>
            </div>
          </div>
        </div>
        <Sparkles className="absolute -right-6 -bottom-6 text-white/10 w-32 h-32 animate-pulse" />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <button onClick={() => setActiveTab('focus')} className={`p-6 rounded-[32px] border-2 flex flex-col items-center gap-3 transition-all hover:scale-[1.02] active:scale-95 ${darkMode ? 'bg-slate-800 border-slate-700 shadow-lg' : 'bg-white border-slate-100 shadow-sm'}`}>
          <div className="p-4 bg-orange-100 dark:bg-orange-500/20 rounded-2xl text-orange-600"><Timer size={32} /></div>
          <span className="font-black text-xs uppercase tracking-widest">Focus</span>
        </button>
        <button onClick={() => setActiveTab('blog')} className={`p-6 rounded-[32px] border-2 flex flex-col items-center gap-3 transition-all hover:scale-[1.02] active:scale-95 ${darkMode ? 'bg-slate-800 border-slate-700 shadow-lg' : 'bg-white border-slate-100 shadow-sm'}`}>
          <div className="p-4 bg-emerald-100 dark:bg-emerald-500/20 rounded-2xl text-emerald-600"><Newspaper size={32} /></div>
          <span className="font-black text-xs uppercase tracking-widest">Insights</span>
        </button>
      </div>

      <AdSenseUnit slot="home_footer_ad" darkMode={darkMode} />
    </div>
  );

  const BlogView = () => (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 text-left pb-16">
      {selectedPost ? (
        <div className="space-y-6">
          <button onClick={() => setSelectedPost(null)} className="flex items-center gap-2 text-indigo-500 font-black text-xs uppercase tracking-widest">
            <ArrowLeft size={16} /> Back to List
          </button>
          <h2 className="text-3xl font-black tracking-tighter leading-tight">{selectedPost.title}</h2>
          <div className="flex items-center gap-4 text-[10px] font-bold opacity-40 uppercase tracking-widest">
            <span>By {selectedPost.author}</span>
            <span>•</span>
            <span>{selectedPost.date}</span>
          </div>
          <div className={`p-8 rounded-[40px] border-2 leading-relaxed text-base font-medium opacity-80 ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-100'}`}>
            {selectedPost.content}
          </div>
          <AdSenseUnit slot="blog_article_ad" darkMode={darkMode} />
        </div>
      ) : (
        <div className="space-y-8">
          <div className="text-left mb-8">
            <h2 className="text-3xl font-black tracking-tighter">ADHD Blog & Tips</h2>
            <p className="opacity-50 text-sm font-medium">Deep dives into neurodivergent productivity.</p>
          </div>
          <div className="grid gap-6">
            {blogPosts.map(post => (
              <article 
                key={post.id}
                onClick={() => setSelectedPost(post)}
                className={`p-6 rounded-[32px] border-2 cursor-pointer transition-all hover:translate-y-[-4px] ${darkMode ? 'bg-slate-800 border-slate-700 hover:shadow-2xl hover:shadow-indigo-500/10' : 'bg-white border-slate-100 hover:shadow-xl'}`}
              >
                <h3 className="font-black text-xl mb-2 tracking-tight">{post.title}</h3>
                <p className="text-sm opacity-60 line-clamp-2 mb-4 font-medium">{post.excerpt}</p>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-black text-indigo-500 uppercase tracking-widest">Read Article</span>
                  <ChevronRight size={16} className="text-indigo-500" />
                </div>
              </article>
            ))}
          </div>
          <AdSenseUnit slot="blog_list_ad" darkMode={darkMode} />
        </div>
      )}
    </div>
  );

  const FocusView = () => (
    <section className="space-y-6 animate-in fade-in slide-in-from-bottom-4">
      <div className={`p-10 rounded-[48px] border-2 flex flex-col items-center transition-all ${darkMode ? 'bg-slate-800 border-slate-700 shadow-2xl' : 'bg-white border-slate-100 shadow-xl'}`}>
        <div className={`w-64 h-64 rounded-full border-[16px] flex flex-col items-center justify-center relative transition-colors duration-1000 ${isBreak ? 'border-emerald-500/20' : 'border-indigo-600/20'}`}>
          <div 
            className={`absolute inset-0 rounded-full border-[16px] transition-all duration-1000 ${isBreak ? 'border-emerald-500' : 'border-indigo-600'}`}
            style={{ clipPath: `inset(${(1 - (timeLeft / (isBreak ? 300 : 1500))) * 100}% 0 0 0)` }}
          />
          <span className="text-[10px] font-black tracking-[0.3em] text-slate-400 mb-2 uppercase text-center block tracking-widest">{isBreak ? 'Break' : 'Focus'}</span>
          <span className="text-7xl font-black tabular-nums tracking-tighter text-center block">{Math.floor(timeLeft / 60)}:{(timeLeft % 60).toString().padStart(2, '0')}</span>
        </div>
        <div className="flex gap-4 w-full mt-10 px-4">
          <button onClick={() => setIsActive(!isActive)} className={`flex-grow py-5 rounded-3xl flex items-center justify-center gap-2 text-white font-black shadow-lg transition-all active:scale-95 ${isActive ? 'bg-amber-500 shadow-amber-500/30' : 'bg-indigo-600 shadow-indigo-500/30'}`}>
            {isActive ? <Pause size={28} /> : <Play size={28} />}
            {isActive ? 'PAUSE' : 'START SESSION'}
          </button>
          <button onClick={() => {setIsActive(false); setTimeLeft(25 * 60);}} className={`p-5 rounded-3xl ${darkMode ? 'bg-slate-700 text-slate-300' : 'bg-slate-100 text-slate-500'} active:scale-95 flex items-center justify-center`}><RotateCcw size={28} /></button>
        </div>
      </div>

      {/* Interactive Music Card */}
      <div className={`p-6 rounded-[32px] border-2 ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-100 shadow-sm'} text-left`}>
        <div className="flex items-center gap-2 mb-4">
          <div className={`p-2 rounded-xl ${currentMusic ? 'bg-indigo-500 text-white animate-pulse' : 'bg-slate-100 dark:bg-slate-900 text-slate-400'}`}><Music size={18} /></div>
          <h3 className="font-black text-sm uppercase tracking-widest text-left">Focus Audio</h3>
          {currentMusic && <span className="ml-auto text-[10px] font-bold text-indigo-500 uppercase animate-pulse">Live</span>}
        </div>
        <div className="grid grid-cols-2 gap-3">
          {musicTracks.map(track => (
            <button 
              key={track.id}
              onClick={() => setCurrentMusic(currentMusic === track.id ? null : track.id)}
              className={`p-3 rounded-2xl border-2 flex flex-col items-start gap-1 transition-all ${
                currentMusic === track.id 
                ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30 scale-[1.02]' 
                : 'border-transparent bg-slate-50 dark:bg-slate-900/40 hover:bg-slate-100'
              }`}
            >
              <div className={`p-2 rounded-xl mb-1 ${currentMusic === track.id ? 'bg-indigo-500 text-white' : 'bg-slate-200 dark:bg-slate-800 text-slate-500'}`}>{track.icon}</div>
              <span className="text-xs font-black text-left">{track.name}</span>
            </button>
          ))}
        </div>
      </div>
      
      <AdSenseUnit slot="focus_bottom_ad" darkMode={darkMode} />
    </section>
  );

  if (!user) return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 dark:bg-slate-900 text-indigo-600 font-black">
      <Sparkles className="animate-pulse mb-6" size={64} />
      <span className="tracking-widest uppercase text-xs">Syncing Missions...</span>
    </div>
  );

  return (
    <div className={`min-h-screen flex flex-col transition-all duration-500 ${darkMode ? 'bg-slate-900 text-slate-100 dark' : 'bg-slate-50 text-slate-800'}`}>
      
      {notification && (
        <div className="fixed top-24 left-4 right-4 z-50 animate-in slide-in-from-top-6 duration-500">
          <div className="bg-indigo-600 text-white p-5 rounded-[32px] shadow-2xl flex items-center justify-between border-2 border-white/20">
            <div className="flex items-center gap-3">
              <Bell className="animate-bounce" size={20} />
              <span className="font-bold text-sm text-left">{notification}</span>
            </div>
            <button onClick={() => setNotification(null)} className="p-1 hover:bg-white/10 rounded-full transition-colors"><X size={20} /></button>
          </div>
        </div>
      )}

      <header className={`p-6 sticky top-0 z-30 backdrop-blur-xl border-b transition-colors ${darkMode ? 'bg-slate-900/80 border-slate-800 shadow-xl' : 'bg-white/80 border-slate-100 shadow-sm'}`}>
        <div className="max-w-md mx-auto w-full flex justify-between items-center">
          <div className="text-left">
            <h1 className="text-2xl font-black text-indigo-500 flex items-center gap-2 tracking-tighter text-left">
              FocusBuddy <Sparkles size={22} className="text-amber-400" />
            </h1>
            <p className="text-[10px] text-slate-400 font-black uppercase tracking-widest text-left">ADHD Assist</p>
          </div>
          
          <div className="flex items-center gap-3">
            <button onClick={() => setDarkMode(!darkMode)} className={`p-3 rounded-2xl border transition-all active:scale-90 flex items-center justify-center ${darkMode ? 'bg-slate-800 text-amber-400 border-slate-700' : 'bg-slate-100 text-indigo-600 border-slate-200'}`}>
              {darkMode ? <Sun size={20} /> : <Moon size={20} />}
            </button>
            <div className="bg-orange-100 dark:bg-orange-900/30 px-4 py-2 rounded-2xl text-orange-600 font-black border border-orange-200 dark:border-orange-800 flex items-center gap-2 shadow-sm">
              <Flame size={18} fill="currentColor" />
              <span className="text-sm tabular-nums font-black">{stats.streak}</span>
            </div>
          </div>
        </div>
      </header>

      <div className="w-full h-1 bg-slate-200 dark:bg-slate-800">
        <div 
          className="h-full bg-gradient-to-r from-indigo-500 to-purple-600 transition-all duration-700" 
          style={{ width: `${tasks.length > 0 ? (tasks.filter(t => t.completed).length / tasks.length) * 100 : 0}%` }}
        />
      </div>

      <main className="flex-grow max-w-md mx-auto w-full px-5 pt-8 pb-32 overflow-y-auto">
        {activeTab === 'home' && <HomeView />}
        {activeTab === 'focus' && <FocusView />}
        {activeTab === 'blog' && <BlogView />}
        {activeTab === 'missions' && (
          <section className="space-y-6 animate-in slide-in-from-bottom-6 duration-300 text-left">
            <div className={`p-6 rounded-[32px] border-2 ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-100 shadow-sm'} text-left`}>
              <form onSubmit={handleAddTask} className="space-y-4 text-left">
                <input 
                  value={newTask} 
                  onChange={(e) => setNewTask(e.target.value)} 
                  placeholder="The next mission?" 
                  className={`w-full p-5 rounded-3xl border-none text-lg font-bold transition-all ${darkMode ? 'bg-slate-900 text-white shadow-inner placeholder:text-slate-800' : 'bg-slate-50 shadow-inner'}`} 
                />
                <div className="flex items-center justify-between">
                  <div className="flex gap-2">
                    {['low', 'medium', 'high'].map(lvl => (
                      <button key={lvl} type="button" onClick={() => setTaskEnergy(lvl)} className={`px-3 py-1.5 rounded-xl text-[10px] font-black uppercase border-2 transition-all ${taskEnergy === lvl ? 'bg-indigo-600 border-indigo-600 text-white' : (darkMode ? 'bg-slate-900 border-slate-700 text-slate-600' : 'bg-white border-slate-100 text-slate-400')}`}>
                        <Zap size={10} fill={taskEnergy === lvl ? "currentColor" : "none"} /> {lvl}
                      </button>
                    ))}
                  </div>
                  <button type="submit" className="bg-indigo-600 text-white px-8 py-2.5 rounded-2xl font-black uppercase text-xs shadow-xl active:scale-95 transition-transform hover:scale-105">Deploy</button>
                </div>
              </form>
            </div>

            <div className="space-y-3 text-left">
              {tasks.sort((a,b) => b.createdAt - a.createdAt).map((t) => (
                <article key={t.id} className={`p-5 rounded-[32px] border-2 flex items-center gap-5 transition-all ${t.completed ? 'opacity-30 border-transparent bg-slate-100 dark:bg-slate-800' : (darkMode ? 'bg-slate-800 border-slate-700 shadow-lg' : 'bg-white border-slate-100 shadow-sm')}`}>
                  <button onClick={() => updateDoc(doc(db, 'artifacts', appId, 'users', user.uid, 'tasks', t.id), { completed: !t.completed })} className={`w-12 h-12 rounded-2xl border-2 flex items-center justify-center transition-all shrink-0 ${t.completed ? 'bg-emerald-500 border-emerald-500 text-white' : (darkMode ? 'border-slate-600' : 'border-slate-200')}`}><CheckCircle2 size={24} /></button>
                  <div className="flex-grow min-w-0 text-left text-left">
                    <span className={`text-[9px] font-black uppercase tracking-widest ${t.energy === 'high' ? 'text-rose-500' : t.energy === 'medium' ? 'text-amber-500' : 'text-emerald-500'}`}>{t.energy} cost</span>
                    <h3 className={`font-black text-lg truncate leading-none text-left ${t.completed ? 'line-through' : ''}`}>{t.text}</h3>
                  </div>
                  <button onClick={() => deleteDoc(doc(db, 'artifacts', appId, 'users', user.uid, 'tasks', t.id))} className="text-slate-300 hover:text-rose-500 transition-colors"><Trash2 size={20}/></button>
                </article>
              ))}
            </div>
            <AdSenseUnit slot="task_list_ad" darkMode={darkMode} />
          </section>
        )}
        {activeTab === 'settings' && <SettingsView />}
      </main>

      <nav className={`fixed bottom-0 left-0 right-0 border-t px-6 py-5 z-40 transition-colors ${darkMode ? 'bg-slate-900/90 border-slate-800 shadow-[0_-10px_30px_rgba(0,0,0,0.5)]' : 'bg-white/90 border-slate-200 shadow-[0_-10px_30px_rgba(0,0,0,0.03)]'} backdrop-blur-2xl`}>
        <div className="max-w-md mx-auto w-full flex justify-between items-center px-4">
          <NavBtn icon={<Home size={28} />} label="Home" active={activeTab === 'home'} onClick={() => {setActiveTab('home'); setSelectedPost(null);}} />
          <NavBtn icon={<Timer size={28} />} label="Focus" active={activeTab === 'focus'} onClick={() => setActiveTab('focus')} />
          <NavBtn icon={<ListTodo size={28} />} label="Missions" active={activeTab === 'missions'} onClick={() => setActiveTab('missions')} />
          <NavBtn icon={<Newspaper size={28} />} label="Insights" active={activeTab === 'blog'} onClick={() => setActiveTab('blog')} />
          <NavBtn icon={<Settings size={28} />} label="Menu" active={activeTab === 'settings'} onClick={() => setActiveTab('settings')} />
        </div>
      </nav>
    </div>
  );
};

const NavBtn = ({ icon, label, active, onClick }) => (
  <button 
    onClick={onClick} 
    className={`flex flex-col items-center gap-1.5 transition-all relative ${active ? 'text-indigo-500 scale-110' : 'text-slate-400 hover:text-slate-500'}`}
  >
    <div className={`transition-transform duration-300 flex items-center justify-center ${active ? 'translate-y-[-3px]' : ''}`}>{icon}</div>
    <span className="text-[9px] font-black uppercase tracking-widest text-center block w-full">{label}</span>
    {active && <div className="absolute -top-1 w-1.5 h-1.5 bg-indigo-500 rounded-full animate-pulse" />}
  </button>
);

const SettingsView = () => (
  <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 text-left pb-20">
    <h2 className="text-3xl font-black tracking-tighter text-left">System</h2>
    <div className="rounded-[40px] border-2 border-slate-100 dark:border-slate-800 overflow-hidden divide-y divide-slate-100 dark:divide-slate-800 bg-white dark:bg-slate-800 shadow-sm text-left">
      <div className="p-6 flex items-center justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors">
        <div className="flex items-center gap-4">
          <ShieldCheck className="text-emerald-500" size={24} />
          <span className="font-bold text-base">Privacy Policy</span>
        </div>
        <ChevronRight size={20} className="opacity-30" />
      </div>
      <div className="p-6 flex items-center justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors">
        <div className="flex items-center gap-4">
          <Mail className="text-rose-500" size={24} />
          <span className="font-bold text-base">Support</span>
        </div>
        <ChevronRight size={20} className="opacity-30" />
      </div>
    </div>
  </div>
);

export default App;
