import { Box, HStack, Icon, Text, Tooltip, VStack } from '@chakra-ui/react';
import { useEffect, useMemo, useState } from 'react';
import { FiCalendar } from 'react-icons/fi';
import { useThemeColors } from '../hooks/useThemeColors';
import { getDataSummary, type DataSummaryCounts } from '../utils/api';

type DataRefreshBadgeProps = {
  dateLabel: string;
  fontSize?: { base: string; md: string } | string;
  compact?: boolean;
};

export const DataRefreshBadge = ({
  dateLabel,
  fontSize = { base: 'xs', md: 'sm' },
  compact = false,
}: DataRefreshBadgeProps) => {
  const colors = useThemeColors();
  const [counts, setCounts] = useState<DataSummaryCounts | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      setLoading(true);
      try {
        const data = await getDataSummary();
        if (!cancelled && data?.counts) setCounts(data.counts);
      } catch {
        // Keep tooltip graceful if endpoint is temporarily unavailable.
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, []);

  const tooltipBody = useMemo(() => {
    if (loading && !counts) {
      return 'Loading data summary...';
    }
    if (!counts) {
      return 'Data summary unavailable';
    }
    return (
      <VStack align="start" spacing={1}>
        <Text fontWeight="bold">System data overview</Text>
        <Text>{counts.projects.toLocaleString()} Projects</Text>
        <Text>{counts.deliverables.toLocaleString()} Deliverables</Text>
        <Text>{counts.partners.toLocaleString()} Partners</Text>
        <Text>{counts.publications.toLocaleString()} Publications</Text>
        <Text>{counts.authors.toLocaleString()} Authors</Text>
      </VStack>
    );
  }, [counts, loading]);

  return (
    <Tooltip
      hasArrow
      placement="top"
      label={tooltipBody}
      bg="gray.800"
      color="white"
      px={3}
      py={2}
      borderRadius="md"
      fontSize="sm"
      openDelay={200}
    >
      <HStack
        spacing={2}
        px={compact ? 2.5 : 3}
        py={compact ? 1 : 1.5}
        borderRadius="full"
        bg={colors.gradientLight}
        border="1px solid"
        borderColor={colors.cardBorder}
        color={colors.primary}
        whiteSpace="nowrap"
        cursor="help"
      >
        <Box
          p={compact ? 1 : 1.5}
          borderRadius="full"
          bg={colors.cardBg}
          border="1px solid"
          borderColor={colors.cardBorder}
          display="inline-flex"
          alignItems="center"
          justifyContent="center"
        >
          <Icon as={FiCalendar} boxSize={compact ? 3 : 3.5} />
        </Box>
        <Text fontSize={fontSize} fontWeight="semibold">
          Last data refresh: {dateLabel}
        </Text>
      </HStack>
    </Tooltip>
  );
};
