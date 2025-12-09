import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { ProductInputScreen } from './src/screens/ProductInputScreen';
import { RecommendationScreen } from './src/screens/RecommendationScreen';
import { InvoiceDetailsScreen } from './src/screens/InvoiceDetailsScreen';
import type { RootStackParamList } from './src/navigation/types';

const Stack = createStackNavigator<RootStackParamList>();
const queryClient = new QueryClient();

export default function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <QueryClientProvider client={queryClient}>
        <NavigationContainer>
          <StatusBar style="dark" backgroundColor="#F9FAFB" translucent={false} />
          <Stack.Navigator
          initialRouteName="ProductInput"
          screenOptions={{
            headerStyle: {
              backgroundColor: '#3B82F6',
            },
            headerTintColor: '#FFFFFF',
            headerTitleStyle: {
              fontWeight: 'bold',
            },
          }}
        >
          <Stack.Screen
            name="ProductInput"
            component={ProductInputScreen}
            options={{
              title: 'Product Search',
              headerShown: false,
            }}
          />
          <Stack.Screen
            name="Recommendation"
            component={RecommendationScreen}
            options={{
              title: 'Recommendations',
            }}
          />
          <Stack.Screen
            name="InvoiceDetails"
            component={InvoiceDetailsScreen}
            options={{
              headerShown: false,
            }}
          />
        </Stack.Navigator>
        </NavigationContainer>
      </QueryClientProvider>
    </GestureHandlerRootView>
  );
}

