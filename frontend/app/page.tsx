import Link from "next/link";

export default function Home() {
  return (
    <main className="landing">
      <header className="landing-nav">
        <Link className="brand" href="/"><span className="brand-mark">✳</span> Framewise</Link>
        <Link className="nav-link" href="/dashboard">Open studio <span>↗</span></Link>
      </header>
      <section className="hero">
        <div className="hero-copy">
          <div className="eyebrow"><span className="status-dot" /> STORY FIRST. SURPRISE-FREE ALWAYS.</div>
          <h1>Your ideas,<br />frame by <em>frame.</em></h1>
          <p>Shape a story, review every scene, and make a video with the cost and time visible before you press go.</p>
          <div className="hero-actions">
            <Link href="/projects/new" className="button button-primary">Create your first video <span>→</span></Link>
            <Link href="/dashboard" className="button button-secondary">Explore the studio</Link>
          </div>
          <div className="hero-footnote"><span>✦</span> Human reviewed at every step <i /> No hidden credits or surprise charges</div>
        </div>
        <div className="hero-art" aria-label="Storyboard preview">
          <div className="art-glow" />
          <div className="art-card art-card-back"><span>SCENE 02</span><div className="art-moon" /></div>
          <div className="art-card art-card-front"><span>SCENE 01&nbsp;&nbsp; · &nbsp;&nbsp;THE DISCOVERY</span><div className="art-orb" /><div className="art-title">THE<br />DEEP<br /><i>REMEMBERS</i></div><div className="art-caption">a story in 6 frames</div></div>
          <div className="art-stamp"><b>01—06</b><span>YOUR STORY<br />BOARD</span></div>
          <div className="art-label">A RETIRED ASTRONAUT<br />DISCOVERS AN OCEAN WORLD</div>
        </div>
      </section>
      <section className="landing-bottom">
        <span>MADE FOR PEOPLE WITH A STORY TO TELL</span>
        <div><b>01</b> Plan with clarity</div><div><b>02</b> Review the details</div><div><b>03</b> Export on your terms</div>
      </section>
    </main>
  );
}
