import React, { useState, useEffect, useRef } from 'react';

interface LazyImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  src: string;
  alt: string;
  placeholder?: React.ReactNode;
  fallbackIcon?: React.ReactNode;
}

export const LazyImage: React.FC<LazyImageProps> = ({
  src,
  alt,
  className = '',
  placeholder,
  fallbackIcon,
  onError,
  ...props
}) => {
  const [isInView, setIsInView] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);
  const [hasError, setHasError] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setIsLoaded(false);
    setHasError(false);

    if (!('IntersectionObserver' in window)) {
      setIsInView(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsInView(true);
          observer.disconnect();
        }
      },
      {
        rootMargin: '200px'
      }
    );

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => {
      observer.disconnect();
    };
  }, [src]);

  return (
    <div ref={containerRef} className="w-full h-full relative overflow-hidden bg-dark-850">
      {/* Skeleton while not in view or while downloading */}
      {(!isInView || !isLoaded) && !hasError && (
        <div className="absolute inset-0 bg-dark-800/80 animate-pulse flex items-center justify-center">
          {placeholder}
        </div>
      )}

      {/* Error Fallback */}
      {hasError && (
        <div className="absolute inset-0 bg-gradient-to-br from-dark-800 to-dark-900 flex flex-col items-center justify-center p-3 text-center">
          {fallbackIcon}
          <span className="text-[10px] text-gray-500 line-clamp-2 mt-1">{alt}</span>
        </div>
      )}

      {/* Actual Image only requested once within viewport threshold */}
      {isInView && !hasError && (
        <img
          src={src}
          alt={alt}
          onLoad={() => setIsLoaded(true)}
          onError={(e) => {
            setHasError(true);
            onError?.(e);
          }}
          className={`${className} ${isLoaded ? 'opacity-100' : 'opacity-0'} transition-opacity duration-300`}
          {...props}
        />
      )}
    </div>
  );
};
