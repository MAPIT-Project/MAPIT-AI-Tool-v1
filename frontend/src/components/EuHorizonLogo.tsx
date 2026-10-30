import {
  Box,
  Image,
  Tooltip,
  VisuallyHidden,
  useColorModeValue,
} from '@chakra-ui/react';
import type { ResponsiveValue } from '@chakra-ui/styled-system';
import { EU_FUNDING_ARIA_LABEL, EU_FUNDING_TOOLTIP } from '../config/funding';

// Optional: add official artwork to src/assets/eu_horizon_logo.png and uncomment the import:
// import euHorizonLogoAsset from '../assets/eu_horizon_logo.png';
const euHorizonLogoAsset: string | undefined = undefined;

type EuHorizonLogoProps = {
  /** Height of the logo area (width scales automatically). */
  height?: ResponsiveValue<string | number>;
  /** Tooltip placement relative to the logo. */
  tooltipPlacement?: 'top' | 'bottom' | 'left' | 'right';
  /** Override default tooltip copy (e.g. per-page). */
  tooltipLabel?: string;
};

/**
 * Placeholder Horizon Europe / EU branding with tooltip.
 * Replace `EU_FUNDING_TOOLTIP` in config/funding.ts or pass `tooltipLabel`.
 * To use an image asset, set `euHorizonLogoAsset` in this file.
 */
export function EuHorizonLogo({
  height = { base: '48px', md: '60px' },
  tooltipPlacement = 'bottom',
  tooltipLabel = EU_FUNDING_TOOLTIP,
}: EuHorizonLogoProps) {
  const logoOpacity = useColorModeValue(0.72, 1);
  const logoFilter = useColorModeValue('saturate(0.9) contrast(0.95)', 'none');

  const logo = euHorizonLogoAsset ? (
    <Image
      src={euHorizonLogoAsset}
      alt={EU_FUNDING_ARIA_LABEL}
      h={height}
      w="auto"
      maxW="140px"
      objectFit="contain"
    />
  ) : (
    <HorizonEuropePlaceholder height={height} />
  );

  return (
    <Tooltip
      label={tooltipLabel}
      hasArrow
      placement={tooltipPlacement}
      maxW="560px"
      fontSize="sm"
      lineHeight="tall"
      openDelay={300}
      closeOnClick={false}
      bg="gray.800"
      color="white"
      px={3}
      py={2}
      borderRadius="md"
    >
      <Box
        as="span"
        display="inline-flex"
        alignItems="center"
        cursor="help"
        role="img"
        aria-label={EU_FUNDING_ARIA_LABEL}
        tabIndex={0}
        opacity={logoOpacity}
        filter={logoFilter}
        _hover={{ opacity: 1 }}
        _focusVisible={{
          outline: '2px solid',
          outlineColor: 'blue.400',
          outlineOffset: '2px',
          borderRadius: 'md',
        }}
      >
        {logo}
        <VisuallyHidden>{tooltipLabel}</VisuallyHidden>
      </Box>
    </Tooltip>
  );
}

const STAR_ANGLES = Array.from({ length: 12 }, (_, i) => (i * 30 - 90) * (Math.PI / 180));

/** Inline SVG placeholder until an official logo asset is added. */
function HorizonEuropePlaceholder({ height }: { height: ResponsiveValue<string | number> }) {
  return (
    <Box h={height} minW="140px" maxW="220px" w="auto" flexShrink={0} aria-hidden>
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 200 40"
        width="100%"
        height="100%"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <linearGradient id="mapit-he-bg" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#003399" />
            <stop offset="100%" stopColor="#0055b8" />
          </linearGradient>
        </defs>
        <rect width="200" height="40" rx="7" fill="url(#mapit-he-bg)" />
        <circle cx="22" cy="20" r="14" fill="none" stroke="#FFCC00" strokeWidth="1.2" />
        {STAR_ANGLES.map((angle, i) => (
          <circle
            key={i}
            cx={22 + 10 * Math.cos(angle)}
            cy={20 + 10 * Math.sin(angle)}
            r="1.8"
            fill="#FFCC00"
          />
        ))}
        <text
          x="44"
          y="17"
          fill="#ffffff"
          fontSize="11"
          fontFamily="system-ui, Arial, sans-serif"
          fontWeight="600"
        >
          Horizon Europe
        </text>
        <text
          x="44"
          y="30"
          fill="#cce0ff"
          fontSize="8"
          fontFamily="system-ui, Arial, sans-serif"
          fontWeight="500"
        >
          EU-funded project
        </text>
      </svg>
    </Box>
  );
}
