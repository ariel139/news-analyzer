import { useEffect, useRef } from "react";
import { Route, Routes, useLocation, type Location } from "react-router-dom";
import { DataProvider } from "./data";
import { ArticlePage } from "./pages/ArticlePage";
import { Drawer } from "./pages/Drawer";
import { FeedPage } from "./pages/FeedPage";
import { MethodologyPage } from "./pages/MethodologyPage";
import { NotFoundPage } from "./pages/NotFoundPage";

/**
 * A card click navigates to /article/:id with the feed as `background`: the feed stays mounted
 * (filters, loaded pages, scroll) and the article opens in a drawer on top. A direct visit to
 * /article/:id has no background and renders the full page.
 */
export default function App() {
  const location = useLocation();
  const background = (location.state as { background?: Location } | null)?.background;

  // New pages start at the top, but opening or closing the drawer must not move the feed.
  const hadBackground = useRef(false);
  useEffect(() => {
    if (!background && !hadBackground.current) window.scrollTo(0, 0);
    hadBackground.current = !!background;
  }, [location.pathname, background]);

  return (
    <DataProvider>
      <Routes location={background ?? location}>
        <Route path="/" element={<FeedPage />} />
        <Route path="/article/:id" element={<ArticlePage />} />
        <Route path="/methodology" element={<MethodologyPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      {background && (
        <Routes>
          <Route path="/article/:id" element={<Drawer background={background} />} />
        </Routes>
      )}
    </DataProvider>
  );
}
