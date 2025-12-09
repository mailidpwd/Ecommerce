import React, { useEffect, useState, useRef } from 'react';
import { View, Text, StyleSheet, Animated, TouchableOpacity, Dimensions } from 'react-native';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

interface LoadingSkeletonProps {
  message?: string;
}

export const LoadingSkeleton: React.FC<LoadingSkeletonProps> = ({ 
  message = 'Analyzing product...' 
}) => {
  const [progress] = useState(new Animated.Value(0));
  const [elapsedTime, setElapsedTime] = useState(0);
  const [currentProcess, setCurrentProcess] = useState('Scraping product data...');
  
  // Mini-game state (Dinosaur Runner!)
  const [score, setScore] = useState(0);
  const [showGame, setShowGame] = useState(false);
  const [gameOver, setGameOver] = useState(false);
  const [isJumping, setIsJumping] = useState(false);
  const [obstacles, setObstacles] = useState<{id: number, position: number}[]>([]);
  const dinoY = useRef(new Animated.Value(0)).current;
  const nextObstacleId = useRef(0);
  const gameLoopRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Animate progress bar (simulates ~30 second total time)
    Animated.timing(progress, {
      toValue: 100,
      duration: 30000, // 30 seconds
      useNativeDriver: false,
    }).start();

    // Update elapsed time every second
    const timeInterval = setInterval(() => {
      setElapsedTime(prev => prev + 1);
    }, 1000);

    // Update process messages every few seconds
    const processInterval = setInterval(() => {
      setElapsedTime(currentTime => {
        if (currentTime < 5) {
          setCurrentProcess('🔍 Scraping product data from Amazon/Flipkart...');
        } else if (currentTime < 10) {
          setCurrentProcess('🤖 Running AI analysis with Gemini...');
        } else if (currentTime < 15) {
          setCurrentProcess('🔎 Finding similar products...');
        } else if (currentTime < 20) {
          setCurrentProcess('💰 Checking prices on Flipkart & Snapdeal...');
        } else if (currentTime < 25) {
          setCurrentProcess('✨ Generating recommendations...');
        } else {
          setCurrentProcess('🎯 Finalizing results...');
        }
        return currentTime;
      });
    }, 2000); // Update every 2 seconds

    return () => {
      clearInterval(timeInterval);
      clearInterval(processInterval);
    };
  }, [progress]);

  // Dinosaur Runner Game Logic
  useEffect(() => {
    // Show game after 3 seconds
    const gameStartTimer = setTimeout(() => {
      setShowGame(true);
    }, 3000);

    if (!showGame || gameOver) return;

    // Spawn obstacles
    const obstacleInterval = setInterval(() => {
      const newObstacle = {
        id: nextObstacleId.current++,
        position: SCREEN_WIDTH - 50, // Start from right
      };
      setObstacles(prev => [...prev, newObstacle]);
    }, 2000); // New obstacle every 2 seconds

    // Game loop - move obstacles and check collision
    gameLoopRef.current = setInterval(() => {
      setObstacles(prev => {
        const updated = prev.map(obs => ({
          ...obs,
          position: obs.position - 5, // Move left
        })).filter(obs => obs.position > -50); // Remove off-screen
        
        // Check collision (simple box collision)
        const dinoX = 50;
        const dinoBottom = 0; // Ground level when not jumping
        
        for (const obs of updated) {
          if (obs.position > dinoX - 30 && obs.position < dinoX + 30) {
            // Obstacle is at dino's X position
            if (!isJumping) {
              // Hit! Game over
              setGameOver(true);
              if (gameLoopRef.current) clearInterval(gameLoopRef.current);
            }
          }
        }
        
        return updated;
      });
      
      // Increase score
      if (!gameOver) {
        setScore(prev => prev + 1);
      }
    }, 50); // 60 FPS

    return () => {
      clearTimeout(gameStartTimer);
      clearInterval(obstacleInterval);
      if (gameLoopRef.current) clearInterval(gameLoopRef.current);
    };
  }, [showGame, gameOver, isJumping]);

  const handleJump = () => {
    if (isJumping || gameOver) return;
    
    setIsJumping(true);
    
    // Jump up
    Animated.sequence([
      Animated.timing(dinoY, {
        toValue: -80, // Jump height
        duration: 300,
        useNativeDriver: true,
      }),
      Animated.timing(dinoY, {
        toValue: 0, // Fall back down
        duration: 300,
        useNativeDriver: true,
      }),
    ]).start(() => {
      setIsJumping(false);
    });
  };

  const restartGame = () => {
    setGameOver(false);
    setScore(0);
    setObstacles([]);
    dinoY.setValue(0);
  };

  return (
    <View style={styles.container}>
      {/* Main Message */}
      <Text style={styles.message}>{message}</Text>
      
      {/* Elapsed Time */}
      <Text style={styles.timeText}>{elapsedTime}s elapsed</Text>

      {/* Progress Bar Container */}
      <View style={styles.progressBarContainer}>
        <Animated.View
          style={[
            styles.progressBarFill,
            {
              width: progress.interpolate({
                inputRange: [0, 100],
                outputRange: ['0%', '100%'],
              }),
            },
          ]}
        />
      </View>

      {/* Progress Percentage */}
      <Animated.Text style={styles.percentText}>
        {progress.interpolate({
          inputRange: [0, 100],
          outputRange: ['0%', '100%'],
        })}
      </Animated.Text>

      {/* Current Process */}
      <View style={styles.processContainer}>
        <View style={styles.pulseIndicator} />
        <Text style={styles.processText}>{currentProcess}</Text>
      </View>

      {/* Mini-Game: Dinosaur Runner! (Shows after 3 seconds) */}
      {showGame && (
        <View style={styles.gameContainer}>
          <View style={styles.gameHeader}>
            <Text style={styles.gameTitle}>🦖 Dino Runner</Text>
            <Text style={styles.scoreText}>Score: {score}</Text>
          </View>
          
          <TouchableOpacity 
            style={styles.gameArea}
            onPress={handleJump}
            activeOpacity={1}
          >
            {/* Ground */}
            <View style={styles.ground} />
            
            {/* Dinosaur */}
            <Animated.View 
              style={[
                styles.dino,
                { transform: [{ translateY: dinoY }] }
              ]}
            >
              <Text style={styles.dinoEmoji}>🦖</Text>
            </Animated.View>
            
            {/* Obstacles */}
            {obstacles.map(obs => (
              <View
                key={obs.id}
                style={[styles.obstacle, { left: obs.position }]}
              >
                <Text style={styles.obstacleEmoji}>🌵</Text>
              </View>
            ))}
            
            {/* Game Over Overlay */}
            {gameOver && (
              <View style={styles.gameOverOverlay}>
                <Text style={styles.gameOverText}>Game Over! 💀</Text>
                <Text style={styles.finalScoreText}>Score: {score}</Text>
                <TouchableOpacity style={styles.restartButton} onPress={restartGame}>
                  <Text style={styles.restartButtonText}>🔄 Play Again</Text>
                </TouchableOpacity>
              </View>
            )}
            
            {!gameOver && obstacles.length === 0 && (
              <Text style={styles.gameHint}>Tap to jump! 🦖</Text>
            )}
          </TouchableOpacity>
          
          <Text style={styles.gameSubtext}>
            {gameOver ? 'Nice try! Results loading...' : 'Keep jumping while we find deals! 🛍️'}
          </Text>
        </View>
      )}

      {/* Process Steps */}
      <View style={styles.stepsContainer}>
        <View style={styles.stepItem}>
          <Text style={styles.stepIcon}>✅</Text>
          <Text style={styles.stepText}>Scraping product data</Text>
        </View>
        <View style={styles.stepItem}>
          <Text style={styles.stepIcon}>{elapsedTime >= 5 ? '✅' : '⏳'}</Text>
          <Text style={styles.stepText}>Running AI analysis</Text>
        </View>
        <View style={styles.stepItem}>
          <Text style={styles.stepIcon}>{elapsedTime >= 15 ? '✅' : '⏳'}</Text>
          <Text style={styles.stepText}>Finding alternatives</Text>
        </View>
        <View style={styles.stepItem}>
          <Text style={styles.stepIcon}>{elapsedTime >= 20 ? '✅' : '⏳'}</Text>
          <Text style={styles.stepText}>Checking prices</Text>
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
    backgroundColor: '#F9FAFB',
  },
  message: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111827',
    textAlign: 'center',
    marginBottom: 8,
  },
  timeText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#3B82F6',
    marginBottom: 24,
  },
  progressBarContainer: {
    width: '100%',
    height: 12,
    backgroundColor: '#E5E7EB',
    borderRadius: 6,
    overflow: 'hidden',
    marginBottom: 12,
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: '#3B82F6',
    borderRadius: 6,
  },
  percentText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#3B82F6',
    marginBottom: 24,
  },
  processContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 32,
    gap: 12,
  },
  pulseIndicator: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#10B981',
  },
  processText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    textAlign: 'center',
  },
  stepsContainer: {
    width: '100%',
    gap: 12,
  },
  stepItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 8,
    paddingHorizontal: 16,
    backgroundColor: '#FFFFFF',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  stepIcon: {
    fontSize: 18,
  },
  stepText: {
    fontSize: 14,
    color: '#6B7280',
    flex: 1,
  },
  // Dinosaur Runner Game Styles
  gameContainer: {
    width: '100%',
    marginVertical: 20,
    padding: 16,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    borderWidth: 3,
    borderColor: '#3B82F6',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 5,
  },
  gameHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  gameTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#1E40AF',
  },
  scoreText: {
    fontSize: 20,
    fontWeight: '900',
    color: '#10B981',
  },
  gameArea: {
    width: '100%',
    height: 180,
    backgroundColor: '#E0F2FE',
    borderRadius: 12,
    marginBottom: 12,
    position: 'relative',
    overflow: 'hidden',
    justifyContent: 'flex-end',
  },
  ground: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: 4,
    backgroundColor: '#64748B',
  },
  dino: {
    position: 'absolute',
    left: 50,
    bottom: 4,
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  dinoEmoji: {
    fontSize: 36,
  },
  obstacle: {
    position: 'absolute',
    bottom: 4,
    width: 30,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  obstacleEmoji: {
    fontSize: 32,
  },
  gameOverOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 12,
  },
  gameOverText: {
    fontSize: 24,
    fontWeight: '900',
    color: '#FFFFFF',
  },
  finalScoreText: {
    fontSize: 18,
    fontWeight: '700',
    color: '#10B981',
  },
  restartButton: {
    backgroundColor: '#3B82F6',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 24,
    marginTop: 8,
  },
  restartButtonText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  gameHint: {
    fontSize: 14,
    color: '#64748B',
    fontStyle: 'italic',
    textAlign: 'center',
  },
  gameSubtext: {
    fontSize: 12,
    color: '#6B7280',
    textAlign: 'center',
    fontWeight: '600',
  },
});
