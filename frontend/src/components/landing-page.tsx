"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Scissors,
  Sparkles,
  Youtube,
  Github,
  ArrowRight,
  Play,
  Target,
  ScanFace,
  Type,
  Film,
  MonitorPlay,
  Share2,
  Wand2,
  ChevronDown,
  ExternalLink,
  Check,
  Zap,
  Menu,
  X,
} from "lucide-react";
import { isLandingOnlyModeEnabled } from "@/lib/app-flags";
import { getPublicBillingPlans } from "@/lib/billing-plans";

const HOSTED_APP_URL = "https://hanclipper.com";

function ScrollReveal({
  children,
  className = "",
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.1, rootMargin: "0px 0px -60px 0px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? "translateY(0)" : "translateY(30px)",
        transition: `opacity 0.7s cubic-bezier(0.16, 1, 0.3, 1) ${delay}s, transform 0.7s cubic-bezier(0.16, 1, 0.3, 1) ${delay}s`,
      }}
    >
      {children}
    </div>
  );
}

const FEATURES = [
  {
    icon: ScanFace,
    title: "Face-Centered Cropping",
    description:
      "MediaPipe + OpenCV detects and tracks faces for perfect 9:16 vertical framing.",
  },
  {
    icon: Type,
    title: "Word-Synced Captions",
    description:
      "Word-level timestamps power perfectly timed, animated captions on every clip.",
  },
  {
    icon: Target,
    title: "Virality Scoring",
    description:
      "AI rates hook, engagement, value, and shareability — scored 0 to 100.",
  },
  {
    icon: Film,
    title: "B-Roll Overlays",
    description:
      "Automatically source and overlay relevant stock footage from Pexels.",
  },
  {
    icon: Sparkles,
    title: "Caption Templates",
    description:
      "Multiple animation styles and font presets to match your brand.",
  },
  {
    icon: MonitorPlay,
    title: "Platform Export",
    description:
      "One-click presets for TikTok, Reels, and Shorts with optimized encoding.",
  },
];

function getPlans() {
  return [
    {
      name: "Self-Hosted",
      price: "$0",
      period: "forever",
      description: "Run on your own infrastructure with full control.",
      features: [
        "Face-centered cropping",
        "Word-synced captions",
        "Virality scoring",
        "All export presets",
        "Full source code access",
      ],
      cta: "View on GitHub",
      ctaHref: "https://github.com/FujiwaraChoki/supoclip",
      highlighted: false,
    },
    ...getPublicBillingPlans().map((plan) => ({
      name: plan.name,
      price: `$${plan.priceMonthly}`,
      period: "/month",
      description: plan.description,
      features: [
        `${plan.generationLimit} generations per month`,
        "Everything in Free",
        "B-Roll overlays",
        "Caption templates",
        "Platform export presets",
        ...(plan.id === "scale" ? ["Priority processing"] : ["Early access to new features"]),
      ],
      cta: plan.cta,
      ctaHref: "",
      highlighted: plan.highlighted,
    })),
  ];
}

const STEPS = [
  {
    num: "01",
    title: "Drop a link or file",
    description:
      "Paste any YouTube URL or drag-and-drop your own video file.",
    icon: Youtube,
  },
  {
    num: "02",
    title: "AI finds the gold",
    description:
      "Transcription, virality scoring, and segment detection surface the best moments.",
    icon: Wand2,
  },
  {
    num: "03",
    title: "Export & publish",
    description:
      "Get vertical, captioned, face-tracked clips ready for every platform.",
    icon: Share2,
  },
];

export default function LandingPage() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const authEnabled = !isLandingOnlyModeEnabled;

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      {/* ─── NAV ─── */}
      <nav
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          scrolled
            ? "bg-slate-950/80 backdrop-blur-xl border-b border-slate-800 shadow-lg"
            : "bg-transparent"
        }`}
      >
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white font-bold text-sm shadow-lg shadow-violet-500/20">
              H
            </div>
            <span
              className="text-lg font-bold tracking-tight text-white"
              style={{
                fontFamily:
                  "var(--font-syne), var(--font-geist-sans), system-ui",
              }}
            >
              HanClipper
            </span>
          </Link>

          <div className="hidden md:flex items-center gap-8">
            <a
              href="#how-it-works"
              className="text-sm text-slate-400 hover:text-violet-400 transition-colors"
            >
              How It Works
            </a>
            <a
              href="#features"
              className="text-sm text-slate-400 hover:text-violet-400 transition-colors"
            >
              Features
            </a>
            <a
              href="#pricing"
              className="text-sm text-slate-400 hover:text-violet-400 transition-colors"
            >
              Pricing
            </a>
            <a
              href="#open-source"
              className="text-sm text-slate-400 hover:text-violet-400 transition-colors"
            >
              Open Source
            </a>
          </div>

          {/* Desktop auth buttons */}
          <div className="hidden md:flex items-center gap-3">
            {authEnabled ? (
              <>
                <Link href="/sign-in">
                  <Button variant="ghost" size="sm" className="text-slate-300 hover:text-white hover:bg-slate-800">
                    Sign In
                  </Button>
                </Link>
                <Link href="/sign-up">
                  <Button size="sm" className="bg-violet-600 hover:bg-violet-500 text-white shadow-lg shadow-violet-500/25">
                    Get Started
                  </Button>
                </Link>
              </>
            ) : (
              <a href={HOSTED_APP_URL} target="_blank" rel="noopener noreferrer">
                <Button size="sm" className="bg-violet-600 hover:bg-violet-500 text-white">
                  Open Hosted App
                  <ExternalLink className="w-3.5 h-3.5" />
                </Button>
              </a>
            )}
          </div>

          {/* Mobile hamburger */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setMobileNavOpen(!mobileNavOpen)}
            className="md:hidden p-2 text-slate-300"
            aria-label="Toggle menu"
          >
            {mobileNavOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </Button>
        </div>

        {/* Mobile nav dropdown */}
        {mobileNavOpen && (
          <div className="md:hidden border-t border-slate-800 bg-slate-950/95 backdrop-blur-xl">
            <div className="max-w-6xl mx-auto px-6 py-4 space-y-1">
              <a
                href="#how-it-works"
                onClick={() => setMobileNavOpen(false)}
                className="block rounded-lg px-3 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-slate-800/50 transition-colors"
              >
                How It Works
              </a>
              <a
                href="#features"
                onClick={() => setMobileNavOpen(false)}
                className="block rounded-lg px-3 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-slate-800/50 transition-colors"
              >
                Features
              </a>
              <a
                href="#pricing"
                onClick={() => setMobileNavOpen(false)}
                className="block rounded-lg px-3 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-slate-800/50 transition-colors"
              >
                Pricing
              </a>
              <a
                href="#open-source"
                onClick={() => setMobileNavOpen(false)}
                className="block rounded-lg px-3 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-slate-800/50 transition-colors"
              >
                Open Source
              </a>
              <Separator className="my-2 bg-slate-800" />
              <div className="flex flex-col gap-2 px-3 pt-1">
                {authEnabled ? (
                  <>
                    <Link href="/sign-in" onClick={() => setMobileNavOpen(false)}>
                      <Button variant="outline" size="sm" className="w-full border-slate-700 text-slate-300">
                        Sign In
                      </Button>
                    </Link>
                    <Link href="/sign-up" onClick={() => setMobileNavOpen(false)}>
                      <Button size="sm" className="w-full bg-violet-600 hover:bg-violet-500 text-white">Get Started</Button>
                    </Link>
                  </>
                ) : (
                  <a href={HOSTED_APP_URL} target="_blank" rel="noopener noreferrer">
                    <Button size="sm" className="w-full bg-violet-600 hover:bg-violet-500 text-white">
                      Open Hosted App
                      <ExternalLink className="w-3.5 h-3.5" />
                    </Button>
                  </a>
                )}
              </div>
            </div>
          </div>
        )}
      </nav>

      {/* ─── HERO ─── */}
      <section className="relative pt-32 pb-20 md:pt-40 md:pb-28 overflow-hidden">
        {/* Background effects */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-violet-600/20 blur-[120px]" />
          <div className="absolute -bottom-40 -left-40 w-96 h-96 rounded-full bg-indigo-600/20 blur-[120px]" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-violet-500/5 blur-[150px]" />
        </div>

        {/* Grid pattern overlay */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              "radial-gradient(circle at 1px 1px, white 1px, transparent 0)",
            backgroundSize: "32px 32px",
          }}
        />

        <div className="relative max-w-6xl mx-auto px-6">
          <div className="grid lg:grid-cols-2 gap-16 lg:gap-20 items-center">
            {/* Left: Text */}
            <div>
              <Badge
                className="mb-6 gap-2 bg-violet-500/10 text-violet-300 border-violet-500/20"
                style={{ animation: "landing-fade-in-up 0.6s ease-out both" }}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
                Open Source & Self-Hostable
              </Badge>

              <h1
                className="text-4xl sm:text-5xl lg:text-[3.5rem] font-extrabold leading-[1.08] tracking-tight text-white mb-6"
                style={{
                  fontFamily:
                    "var(--font-syne), var(--font-geist-sans), system-ui",
                  animation: "landing-fade-in-up 0.6s ease-out 0.1s both",
                }}
              >
                Clip smarter,
                <br />
                <span className="bg-gradient-to-r from-violet-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent">
                  grow faster
                </span>
              </h1>

              <p
                className="text-base sm:text-lg text-slate-400 leading-relaxed max-w-lg mb-10"
                style={{
                  animation: "landing-fade-in-up 0.6s ease-out 0.2s both",
                }}
              >
                HanClipper uses AI to find your video's best moments, crop for
                vertical, add word-synced captions, and export ready-to-post
                shorts — all in minutes.
              </p>

              <div
                className="flex flex-wrap gap-3 mb-10"
                style={{
                  animation: "landing-fade-in-up 0.6s ease-out 0.3s both",
                }}
              >
                {authEnabled ? (
                  <Link href="/sign-up">
                    <Button size="lg" className="px-8 h-12 text-sm bg-violet-600 hover:bg-violet-500 text-white shadow-xl shadow-violet-500/25">
                      Start Clipping Free
                      <ArrowRight className="w-4 h-4" />
                    </Button>
                  </Link>
                ) : (
                  <a href={HOSTED_APP_URL} target="_blank" rel="noopener noreferrer">
                    <Button size="lg" className="px-8 h-12 text-sm bg-violet-600 hover:bg-violet-500 text-white shadow-xl shadow-violet-500/25">
                      Use Hosted App
                      <ExternalLink className="w-4 h-4" />
                    </Button>
                  </a>
                )}
                <a
                  href="https://github.com/FujiwaraChoki/supoclip"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Button variant="outline" size="lg" className="px-8 h-12 text-sm border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white">
                    <Github className="w-4 h-4" />
                    View Source
                  </Button>
                </a>
              </div>

              <div
                className="flex flex-wrap gap-x-6 gap-y-2 text-xs text-slate-500"
                style={{
                  animation: "landing-fade-in-up 0.6s ease-out 0.4s both",
                }}
              >
                {[
                  { icon: ScanFace, label: "9:16 Auto-Crop" },
                  { icon: Type, label: "Word-Synced Captions" },
                  { icon: Target, label: "Virality Scoring" },
                ].map(({ icon: Icon, label }) => (
                  <div key={label} className="flex items-center gap-1.5">
                    <Icon className="w-3.5 h-3.5 text-violet-400" />
                    {label}
                  </div>
                ))}
              </div>
            </div>

            {/* Right: Visual */}
            <div
              className="relative flex justify-center lg:justify-end"
              style={{ animation: "landing-fade-in-up 0.8s ease-out 0.3s both" }}
            >
              <HeroVisual />
            </div>
          </div>
        </div>

        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 hidden md:block">
          <ChevronDown className="w-5 h-5 text-slate-600 animate-bounce" />
        </div>
      </section>

      <Separator className="bg-slate-800" />

      {/* ─── HOW IT WORKS ─── */}
      <section id="how-it-works" className="py-20 md:py-28">
        <div className="max-w-6xl mx-auto px-6">
          <ScrollReveal className="text-center mb-14">
            <p className="text-xs font-semibold tracking-[0.2em] uppercase text-violet-400 mb-3">
              How It Works
            </p>
            <h2
              className="text-3xl sm:text-4xl font-bold tracking-tight text-white"
              style={{
                fontFamily:
                  "var(--font-syne), var(--font-geist-sans), system-ui",
              }}
            >
              Three steps. Zero effort.
            </h2>
          </ScrollReveal>

          <div className="grid md:grid-cols-3 gap-6">
            {STEPS.map((step, i) => (
              <ScrollReveal key={step.num} delay={i * 0.1}>
                <Card className="h-full py-0 gap-0 bg-slate-900/50 border-slate-800 hover:border-violet-500/30 hover:shadow-lg hover:shadow-violet-500/5 transition-all duration-300">
                  <CardContent className="p-8">
                    <span
                      className="text-6xl font-black leading-none block mb-6 text-slate-700 select-none"
                      style={{ fontFamily: "var(--font-syne), system-ui" }}
                    >
                      {step.num}
                    </span>
                    <div className="w-10 h-10 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center mb-5">
                      <step.icon className="w-5 h-5 text-violet-400" />
                    </div>
                    <h3
                      className="text-lg font-semibold mb-2 text-white"
                      style={{ fontFamily: "var(--font-syne), system-ui" }}
                    >
                      {step.title}
                    </h3>
                    <p className="text-sm text-slate-400 leading-relaxed">
                      {step.description}
                    </p>
                  </CardContent>
                </Card>
              </ScrollReveal>
            ))}
          </div>
        </div>
      </section>

      <Separator className="bg-slate-800" />

      {/* ─── FEATURES ─── */}
      <section id="features" className="py-20 md:py-28">
        <div className="max-w-6xl mx-auto px-6">
          <ScrollReveal className="text-center mb-14">
            <p className="text-xs font-semibold tracking-[0.2em] uppercase text-violet-400 mb-3">
              Features
            </p>
            <h2
              className="text-3xl sm:text-4xl font-bold tracking-tight mb-4 text-white"
              style={{
                fontFamily:
                  "var(--font-syne), var(--font-geist-sans), system-ui",
              }}
            >
              Everything you need to go viral
            </h2>
            <p className="text-sm text-slate-400 max-w-md mx-auto">
              Professional-grade AI video clipping at every step of the pipeline.
            </p>
          </ScrollReveal>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {FEATURES.map((feature, i) => (
              <ScrollReveal key={feature.title} delay={i * 0.07}>
                <Card className="h-full py-0 gap-0 bg-slate-900/50 border-slate-800 hover:border-violet-500/30 hover:shadow-lg hover:shadow-violet-500/5 transition-all duration-300 hover:-translate-y-1">
                  <CardContent className="p-6">
                    <div className="w-10 h-10 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center mb-4">
                      <feature.icon className="w-5 h-5 text-violet-400" />
                    </div>
                    <h3 className="font-semibold mb-2 text-white">{feature.title}</h3>
                    <p className="text-sm text-slate-400 leading-relaxed">
                      {feature.description}
                    </p>
                  </CardContent>
                </Card>
              </ScrollReveal>
            ))}
          </div>
        </div>
      </section>

      <Separator className="bg-slate-800" />

      {/* ─── PRICING ─── */}
      <section id="pricing" className="relative py-20 md:py-28 overflow-hidden">
        {/* Decorative glow */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full bg-violet-500/3 blur-[150px]" />
        </div>

        <div className="relative max-w-5xl mx-auto px-6">
          <ScrollReveal className="text-center mb-16">
            <p className="text-xs font-semibold tracking-[0.2em] uppercase text-violet-400 mb-3">
              Pricing
            </p>
            <h2
              className="text-3xl sm:text-4xl font-bold tracking-tight mb-4 text-white"
              style={{
                fontFamily:
                  "var(--font-syne), var(--font-geist-sans), system-ui",
              }}
            >
              Simple pricing, no surprises
            </h2>
            <p className="text-sm text-slate-400 max-w-md mx-auto">
              Start free. Upgrade when you need more generations.
              Self-hosters get everything free, always.
            </p>
          </ScrollReveal>

          <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto items-start">
            {getPlans().map((plan, i) => (
              <ScrollReveal key={plan.name} delay={i * 0.12}>
                <Card
                  className={`relative py-0 gap-0 transition-all duration-300 ${
                    plan.highlighted
                      ? "bg-violet-600 border-violet-500 text-white shadow-xl shadow-violet-500/25 md:-mt-4 md:mb-4"
                      : "bg-slate-900/50 border-slate-800 hover:border-violet-500/30 hover:-translate-y-1"
                  }`}
                >
                  {plan.highlighted && (
                    <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
                      <Badge className="bg-white text-violet-700 border-0 shadow-md gap-1.5 px-3 py-1">
                        <Zap className="w-3 h-3" />
                        Most Popular
                      </Badge>
                    </div>
                  )}

                  <CardContent className="p-8">
                    <div className="mb-6">
                      <h3
                        className={`text-lg font-semibold mb-1 ${plan.highlighted ? "text-white" : "text-white"}`}
                        style={{ fontFamily: "var(--font-syne), system-ui" }}
                      >
                        {plan.name}
                      </h3>
                      <p
                        className={`text-sm ${
                          plan.highlighted
                            ? "text-violet-200"
                            : "text-slate-400"
                        }`}
                      >
                        {plan.description}
                      </p>
                    </div>

                    <div className="flex items-baseline gap-1 mb-8">
                      <span
                        className="text-5xl font-extrabold tracking-tight text-white"
                        style={{ fontFamily: "var(--font-syne), system-ui" }}
                      >
                        {plan.price}
                      </span>
                      <span
                        className={`text-sm ${
                          plan.highlighted
                            ? "text-violet-200"
                            : "text-slate-400"
                        }`}
                      >
                        {plan.period}
                      </span>
                    </div>

                    <ul className="space-y-3 mb-8">
                      {plan.features.map((feature) => (
                        <li key={feature} className="flex items-start gap-3 text-sm">
                          <Check
                            className={`w-4 h-4 mt-0.5 shrink-0 ${
                              plan.highlighted
                                ? "text-violet-200"
                                : "text-violet-400"
                            }`}
                          />
                          <span
                            className={
                              plan.highlighted
                                ? "text-violet-100"
                                : "text-slate-300"
                            }
                          >
                            {feature}
                          </span>
                        </li>
                      ))}
                    </ul>

                    {plan.ctaHref ? (
                      <a
                        href={plan.ctaHref}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <Button
                          className="w-full h-11 text-sm border-slate-700 text-slate-300 hover:bg-slate-800"
                          variant="outline"
                          size="lg"
                        >
                          <Github className="w-4 h-4" />
                          {plan.cta}
                          <ExternalLink className="w-3.5 h-3.5 opacity-50" />
                        </Button>
                      </a>
                    ) : authEnabled ? (
                      <Link href="/sign-up">
                        <Button
                          className={`w-full h-11 text-sm ${
                            plan.highlighted
                              ? "bg-white text-violet-700 hover:bg-slate-100"
                              : "bg-violet-600 hover:bg-violet-500 text-white"
                          }`}
                          size="lg"
                        >
                          {plan.cta}
                          <ArrowRight className="w-4 h-4" />
                        </Button>
                      </Link>
                    ) : (
                      <a
                        href={HOSTED_APP_URL}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <Button
                          className={`w-full h-11 text-sm ${
                            plan.highlighted
                              ? "bg-white text-violet-700 hover:bg-slate-100"
                              : "bg-violet-600 hover:bg-violet-500 text-white"
                          }`}
                          size="lg"
                        >
                          Use Hosted App
                          <ExternalLink className="w-4 h-4" />
                        </Button>
                      </a>
                    )}
                  </CardContent>
                </Card>
              </ScrollReveal>
            ))}
          </div>

          <ScrollReveal delay={0.3}>
            <p className="text-center text-xs text-slate-500 mt-10 max-w-md mx-auto">
              Self-hosting? All features are free and unlimited.{" "}
              <a
                href="#open-source"
                className="underline underline-offset-2 text-violet-400 hover:text-violet-300 transition-colors"
              >
                See setup instructions
              </a>
              .
            </p>
          </ScrollReveal>
        </div>
      </section>

      <Separator className="bg-slate-800" />

      {/* ─── OPEN SOURCE ─── */}
      <section id="open-source" className="py-20 md:py-28">
        <div className="max-w-3xl mx-auto px-6">
          <ScrollReveal className="text-center mb-10">
            <Badge className="mb-6 gap-1.5 bg-slate-800 text-slate-300 border-slate-700">
              <Github className="w-3.5 h-3.5" />
              AGPL-3.0 Licensed
            </Badge>
            <h2
              className="text-3xl sm:text-4xl font-bold tracking-tight mb-4 text-white"
              style={{ fontFamily: "var(--font-syne), system-ui" }}
            >
              Built in the open
            </h2>
            <p className="text-sm text-slate-400 max-w-lg mx-auto">
              Fully open source. Self-host on your infrastructure, contribute
              features, or fork it and make it yours.
            </p>
          </ScrollReveal>

          <ScrollReveal delay={0.1}>
            <Card className="py-0 gap-0 bg-slate-900/50 border-slate-800">
              <CardContent className="p-6 md:p-8">
                <p className="text-xs font-medium text-slate-500 mb-3">
                  Get running in 30 seconds:
                </p>
                <div className="bg-slate-950 rounded-lg p-5 font-mono text-sm leading-loose overflow-x-auto border border-slate-800">
                  <div>
                    <span className="text-violet-400">$</span>{" "}
                    <span className="text-slate-300">git clone</span>{" "}
                    <span className="text-slate-600">
                      https://github.com/FujiwaraChoki/supoclip
                    </span>
                  </div>
                  <div>
                    <span className="text-violet-400">$</span>{" "}
                    <span className="text-slate-300">cd</span>{" "}
                    <span className="text-slate-600">supoclip</span>
                  </div>
                  <div>
                    <span className="text-violet-400">$</span>{" "}
                    <span className="text-slate-300">docker-compose up -d</span>
                  </div>
                </div>

                <div className="flex flex-wrap gap-3 mt-6">
                  <a
                    href="https://github.com/FujiwaraChoki/supoclip"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Button className="bg-violet-600 hover:bg-violet-500 text-white">
                      <Github className="w-4 h-4" />
                      View on GitHub
                      <ExternalLink className="w-3.5 h-3.5 opacity-50" />
                    </Button>
                  </a>
                  {authEnabled ? (
                    <Link href="/sign-up">
                      <Button variant="outline" className="border-slate-700 text-slate-300 hover:bg-slate-800">
                        Try the hosted version
                        <ArrowRight className="w-4 h-4" />
                      </Button>
                    </Link>
                  ) : (
                    <a href={HOSTED_APP_URL} target="_blank" rel="noopener noreferrer">
                      <Button variant="outline" className="border-slate-700 text-slate-300 hover:bg-slate-800">
                        Open hosted version
                        <ExternalLink className="w-4 h-4" />
                      </Button>
                    </a>
                  )}
                </div>
              </CardContent>
            </Card>
          </ScrollReveal>
        </div>
      </section>

      <Separator className="bg-slate-800" />

      {/* ─── FINAL CTA ─── */}
      <section className="py-20 md:py-28 relative overflow-hidden">
        {/* Background glow */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full bg-violet-500/10 blur-[120px]" />
        </div>

        <ScrollReveal className="relative max-w-2xl mx-auto px-6 text-center">
          <h2
            className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight mb-6 text-white"
            style={{ fontFamily: "var(--font-syne), system-ui" }}
          >
            Ready to create viral clips?
          </h2>
          <p className="text-base text-slate-400 mb-8">
            Turn your next video into scroll-stopping shorts. Free, open source,
            no credit card needed.
          </p>
          {authEnabled ? (
            <Link href="/sign-up">
              <Button size="lg" className="px-10 h-12 text-sm bg-violet-600 hover:bg-violet-500 text-white shadow-xl shadow-violet-500/25">
                Get Started Free
                <ArrowRight className="w-4 h-4" />
              </Button>
            </Link>
          ) : (
            <a href={HOSTED_APP_URL} target="_blank" rel="noopener noreferrer">
              <Button size="lg" className="px-10 h-12 text-sm bg-violet-600 hover:bg-violet-500 text-white shadow-xl shadow-violet-500/25">
                Open Hosted App
                <ExternalLink className="w-4 h-4" />
              </Button>
            </a>
          )}
        </ScrollReveal>
      </section>


      {/* ─── FOOTER ─── */}
      <footer className="border-t border-slate-800 py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white font-bold text-[10px]">
              H
            </div>
            <span
              className="text-sm font-semibold text-slate-300"
              style={{ fontFamily: "var(--font-syne), system-ui" }}
            >
              HanClipper
            </span>
          </div>
          <div className="flex items-center gap-6 text-xs text-slate-500">
            <a
              href="https://github.com/FujiwaraChoki/supoclip"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-violet-400 transition-colors"
            >
              GitHub
            </a>
            <span>AGPL-3.0</span>
            <span>&copy; {new Date().getFullYear()}</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

/* ─── Hero Visual ─── */
function HeroVisual() {
  return (
    <div className="relative w-full max-w-md">
      <Card className="py-0 gap-0 overflow-hidden shadow-2xl border-slate-700/50 bg-slate-900/80 backdrop-blur">
        <CardContent className="p-5">
          {/* Wide video frame */}
          <div
            className="relative w-full rounded-lg overflow-hidden mb-4 bg-slate-800"
            style={{ aspectRatio: "16/9" }}
          >
            {/* Gradient simulating video content */}
            <div
              className="absolute inset-0 bg-gradient-to-br from-slate-700 via-slate-800 to-slate-900"
            />

            {/* Subtle grid overlay */}
            <div
              className="absolute inset-0 opacity-[0.04]"
              style={{
                backgroundImage:
                  "linear-gradient(white 1px, transparent 1px), linear-gradient(90deg, white 1px, transparent 1px)",
                backgroundSize: "20px 20px",
              }}
            />

            {/* Play button */}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-12 h-12 rounded-full bg-violet-600/80 backdrop-blur-sm flex items-center justify-center shadow-lg shadow-violet-500/20">
                <Play className="w-5 h-5 text-white ml-0.5" />
              </div>
            </div>

            {/* Scanning line */}
            <div
              className="absolute top-0 bottom-0 w-0.5 bg-violet-400/50 landing-scan-line"
              style={{
                boxShadow: "0 0 12px rgba(139, 92, 246, 0.3)",
                animation: "landing-scan-line 3s ease-in-out infinite",
              }}
            />

            {/* Detected clip regions */}
            {[
              { left: "8%", score: 92, delay: 0 },
              { left: "38%", score: 87, delay: 0.15 },
              { left: "68%", score: 78, delay: 0.3 },
            ].map((clip, i) => (
              <div
                key={i}
                className="absolute top-[8%] bottom-[8%] w-[22%] rounded-md border-2 border-violet-500/60 bg-violet-500/5"
                style={{
                  left: clip.left,
                  animation: `landing-clip-pulse 2.5s ease-in-out ${clip.delay}s infinite`,
                }}
              >
                <Badge className="absolute -top-3 left-1/2 -translate-x-1/2 text-[10px] px-1.5 py-0 h-5 bg-violet-600 text-white border-0">
                  {clip.score}%
                </Badge>
              </div>
            ))}

            {/* Timeline bar */}
            <div className="absolute bottom-2 left-3 right-3 h-1 rounded-full overflow-hidden bg-slate-700">
              <div className="h-full w-[65%] rounded-full bg-violet-500/30" />
              {[15, 42, 73].map((pos, i) => (
                <div
                  key={i}
                  className="absolute top-1/2 -translate-y-1/2 w-1 h-2.5 rounded-full bg-violet-400"
                  style={{ left: `${pos}%` }}
                />
              ))}
            </div>
          </div>

          {/* Scissors divider */}
          <div className="flex items-center gap-2 mb-4">
            <div className="flex-1 h-px bg-slate-700" />
            <Scissors className="w-4 h-4 text-violet-400 rotate-90" />
            <div className="flex-1 h-px bg-slate-700" />
          </div>

          {/* Extracted vertical clips */}
          <div className="flex gap-2.5 justify-center">
            {[
              {
                bg: "linear-gradient(135deg, #4c1d95, #6d28d9)",
                score: 92,
                label: "Hook moment",
              },
              {
                bg: "linear-gradient(135deg, #4338ca, #6366f1)",
                score: 87,
                label: "Key insight",
              },
              {
                bg: "linear-gradient(135deg, #5b21b6, #7c3aed)",
                score: 78,
                label: "CTA close",
              },
            ].map((clip, i) => (
              <div
                key={i}
                className="relative flex-1 rounded-lg overflow-hidden border border-slate-700 shadow-lg"
                style={{
                  aspectRatio: "9/16",
                  background: clip.bg,
                  animation: `landing-float ${2.5 + i * 0.3}s ease-in-out ${
                    i * 0.2
                  }s infinite`,
                }}
              >
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-6 h-6 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center shadow-sm">
                    <Play className="w-3 h-3 text-white ml-px" />
                  </div>
                </div>
                <div className="absolute bottom-1.5 left-1 right-1">
                  <div className="text-[7px] text-center font-medium py-0.5 px-1 rounded bg-violet-500 text-white">
                    {clip.label}
                  </div>
                </div>
                <Badge className="absolute top-1 right-1 text-[8px] px-1 py-0 h-4 bg-slate-900/80 text-violet-300 border-0">
                  {clip.score}
                </Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Decorative blur spots */}
      <div className="absolute -top-8 -right-8 w-32 h-32 rounded-full bg-violet-500/20 blur-3xl -z-10" />
      <div className="absolute -bottom-8 -left-8 w-24 h-24 rounded-full bg-indigo-500/15 blur-2xl -z-10" />
    </div>
  );
}
